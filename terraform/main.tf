# Declare variables
variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
}

variable "bucket_name" {
  description = "Name of the S3 bucket for static files"
  type        = string
}

provider "aws" {
  region  = var.aws_region
  profile = "manan" # Use the 'manan' profile
}

# S3 Bucket for static files
resource "aws_s3_bucket" "static_files" {
  bucket = var.bucket_name

  # Enable Object Ownership (BucketOwnerEnforced)
  object_lock_enabled = false
}

# Configure the S3 bucket as a static website
resource "aws_s3_bucket_website_configuration" "static_website" {
  bucket = aws_s3_bucket.static_files.bucket

  index_document {
    suffix = "index.html"
  }

  error_document {
    key = "error.html"
  }
}

# CloudFront Origin Access Identity (OAI)
resource "aws_cloudfront_origin_access_identity" "oai" {
  comment = "OAI for ${var.bucket_name}"
}

# CloudFront Distribution for CDN
resource "aws_cloudfront_distribution" "cdn" {
  origin {
    domain_name = aws_s3_bucket.static_files.bucket_regional_domain_name
    origin_id   = "S3-${var.bucket_name}"

    s3_origin_config {
      origin_access_identity = aws_cloudfront_origin_access_identity.oai.cloudfront_access_identity_path
    }
  }

  enabled             = true
  default_root_object = "index.html"

  default_cache_behavior {
    allowed_methods  = ["GET", "HEAD"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "S3-${var.bucket_name}"

    forwarded_values {
      query_string = false

      cookies {
        forward = "none"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 3600
    max_ttl                = 86400
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
}

# S3 Bucket Policy to restrict access to CloudFront OAI
resource "aws_s3_bucket_policy" "static_files_policy" {
  bucket = aws_s3_bucket.static_files.bucket

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect    = "Allow",
        Principal = {
          AWS = aws_cloudfront_origin_access_identity.oai.iam_arn
        },
        Action   = "s3:GetObject",
        Resource = "${aws_s3_bucket.static_files.arn}/*"
      },
      {
        Effect    = "Deny",
        Principal = "*",
        Action    = "s3:*",
        Resource = [
          "${aws_s3_bucket.static_files.arn}",
          "${aws_s3_bucket.static_files.arn}/*"
        ],
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      }
    ]
  })
}
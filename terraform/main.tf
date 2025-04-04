# terraform/main.tf
provider "aws" {
  region = "us-east-1"
}

# S3 Bucket for static files
resource "aws_s3_bucket" "static_files" {
  bucket = "your-s3-bucket-name"
  acl    = "public-read"

  website {
    index_document = "index.html"
  }
}

# CloudFront Distribution for CDN
resource "aws_cloudfront_distribution" "cdn" {
  origin {
    domain_name = aws_s3_bucket.static_files.bucket_regional_domain_name
    origin_id   = "S3-your-s3-bucket-name"

    s3_origin_config {
      origin_access_identity = ""
    }
  }

  enabled             = true
  default_root_object = "index.html"

  default_cache_behavior {
    allowed_methods  = ["GET", "HEAD"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "S3-your-s3-bucket-name"

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
import os
from pathlib import Path

# Base Directory
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get("DEBUG", "FALSE") == "TRUE"  # Convert string to boolean

# Root URL configuration
ROOT_URLCONF = 'stock_forex_app.urls'

# AWS Configuration
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')  # Changed os.getenv to os.environ.get
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = "stock-forex-app"
AWS_S3_REGION_NAME = "us-east-1"
AWS_S3_CUSTOM_DOMAIN = os.environ.get('AWS_CLOUDFRONT_DOMAIN')
AWS_QUERYSTRING_AUTH = False
AWS_DEFAULT_ACL = None

# Allowed hosts
ALLOWED_HOSTS = ["*"]

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.contenttypes',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.auth',
    'django.contrib.sessions',
    'storages',
    'app'
]

# ... rest of your middleware and other settings ...

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# DynamoDB Configuration
DYNAMODB_TABLES = {
    "NewsCache": "NewsCache",
    "SentimentCache": "SentimentCache",
    "Predictions": "Predictions",
    "UserActivities": "UserActivities",
    "Users": "Users",
}

# Session Configuration
SESSION_ENGINE = 'app.dynamodb_session_backend'
SESSION_COOKIE_AGE = 1209600
AWS_DYNAMODB_SESSION_TABLE_NAME = 'django_sessions'
AWS_DYNAMODB_REGION = os.environ.get('AWS_REGION', 'us-east-1')
import os
from pathlib import Path

# Base Directory
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = "FALSE"

AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')

AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')

AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')

ALLOWED_HOSTS = ["*"]

# Application definition
INSTALLED_APPS = [
    # Django apps...
    'django.contrib.admin',
    'django.contrib.contenttypes',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.auth',  # Required for auth
    'django.contrib.sessions',  # Required for sessions

    # Third-party apps
    'storages',  # for S3 storage
    'app'
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',  # Required for sessions
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',  # Required for authentication
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# DynamoDB Configuration
DYNAMODB_TABLES = {
    "NewsCache": "NewsCache",
    "SentimentCache": "SentimentCache",
    "Predictions": "Predictions",
    "UserActivities": "UserActivities",
    "Users": "Users",
}

ROOT_URLCONF = 'stock_forex_app.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "templates"],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'stock_forex_app.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# settings.py
SESSION_ENGINE = 'app.dynamodb_session_backend'
DYNAMODB_SESSIONS_TABLE_NAME = 'Sessions'
SESSION_COOKIE_AGE = 1209600  # 2 weeks in seconds

# Required for DynamoDB sessions
AWS_DYNAMODB_SESSION_TABLE_NAME = 'django_sessions'
AWS_DYNAMODB_REGION = os.getenv('AWS_REGION', 'us-east-1')


# Internationalization
LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

# Static and Media Files

# S3 Settings
AWS_STORAGE_BUCKET_NAME = "stock-forex-app"
AWS_S3_REGION_NAME = "us-east-1"
AWS_S3_CUSTOM_DOMAIN = os.environ.get('AWS_CLOUDFRONT_DOMAIN')  # Example: d1234abcd.cloudfront.net
AWS_QUERYSTRING_AUTH = False  # No authentication needed for static files
AWS_DEFAULT_ACL = None  # To avoid PublicAccessBlock issues

# Static files (CSS, JavaScript, Images)
STATICFILES_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
STATIC_URL = f"https://d1bomvpkbhm8k4.cloudfront.net/static/"

LOGIN_URL = '/login/'

# Media files (user uploads if any)
DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

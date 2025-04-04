# app/views.py
import os
from datetime import datetime, timedelta

import boto3
import requests
from botocore.exceptions import ClientError, BotoCoreError
from django.conf import settings
from django.core.cache import cache
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth import authenticate, login as auth_login, logout  # Rename Django's login to auth_login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
import joblib
import yfinance as yf
import logging
import boto3
from botocore.exceptions import ClientError
from datetime import datetime, timedelta
import pandas as pd

from app.models import UserActivity, Prediction

# Configure logging
logger = logging.getLogger(__name__)

# Initialize AWS clients with configuration from settings
s3_client = boto3.client(
    's3',
    region_name=settings.AWS_REGION,
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
)

dynamodb = boto3.resource(
    'dynamodb',
    region_name=settings.AWS_REGION,
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
)

# Reference DynamoDB tables
news_cache_table = dynamodb.Table('NewsCache')
sentiment_cache_table = dynamodb.Table('SentimentCache')
predictions_table = dynamodb.Table('Predictions')
user_activities_table = dynamodb.Table('UserActivities')

# Define mappings (replace with your actual mappings)
company_mapping = {
    0: 'ADANIPORTS.NS', 1: 'APOLLOHOSP.NS', 2: 'ASIANPAINT.NS', 3: 'AXISBANK.NS',
    4: 'BAJAJ-AUTO.NS', 5: 'BAJAJFINSV.NS', 6: 'BPCL.NS', 7: 'BRITANNIA.NS', 8: 'CIPLA.NS', 9: 'COALINDIA.NS',
    10: 'DIVISLAB.NS', 11: 'DRREDDY.NS', 12: 'EICHERMOT.NS', 13: 'GRASIM.NS', 14: 'HCLTECH.NS', 15: 'HDFCLIFE.NS',
    16: 'HDFCBANK.NS', 17: 'HEROMOTOCO.NS', 18: 'HINDALCO.NS', 19: 'HINDUNILVR.NS', 20: 'ICICIBANK.NS',
    21: 'INDUSINDBK.NS', 22: 'INFY.NS', 23: 'ITC.NS', 24: 'JIOFIN.NS', 25: 'JSWSTEEL.NS', 26: 'KOTAKBANK.NS',
    27: 'LT.NS', 28: 'LTIM.NS', 29: 'M&M.NS', 30: 'MARUTI.NS', 31: 'NESTLEIND.NS', 32: 'NIFTY50.NS', 33: 'NTPC.NS',
    34: 'ONGC.NS', 35: 'POWERGRD.NS', 36: 'RELIANCE.NS', 37: 'SBILIFE.NS', 38: 'SBIN.NS', 39: 'SUNPHARMA.NS',
    40: 'TCS.NS', 41: 'TATACONSUM.NS', 42: 'TATAMOTORS.NS', 43: 'TATASTEEL.NS', 44: 'TECHM.NS', 45: 'TITAN.NS',
    46: 'ULTRACEMCO.NS', 47: 'UPL.NS', 48: 'WIPRO.NS'
}

forex_mapping = {
    0: 'AUD-USD-ASK.joblib', 1: 'AUD-USD-BID.joblib', 2: 'EUR-USD-ASK.joblib', 3: 'EUR-USD-BID.joblib',
    4: 'GBP-USD-ASK.joblib', 5: 'GBP-USD-BID.joblib', 6: 'NZD-USD-ASK.joblib', 7: 'NZD-USD-BID.joblib',
    8: 'USD-CAD-ASK.joblib', 9: 'USD-CAD-BID.joblib', 10: 'USD-CHF-ASK.joblib', 11: 'USD-CHF-BID.joblib',
    12: 'USD-JPY-ASK.joblib', 13: 'USD-JPY-BID.joblib', 14: 'XAG-USD-ASK.joblib', 15: 'XAG-USD-BID.joblib'
}

@login_required
def api_usage(request):
    """
    Monitor API usage for GNews and AWS Comprehend.
    """
    gnews_daily_counter = cache.get('gnews_daily_counter', 0)
    comprehend_monthly_counter = cache.get('comprehend_monthly_counter', 0)

    return render(request, 'api_usage.html', {
        'gnews_daily_usage': gnews_daily_counter,
        'comprehend_monthly_usage': comprehend_monthly_counter
    })
def rate_limit(view_func):
    def wrapped_view(request, *args, **kwargs):
        user_key = f"rate_limit_{request.user.id}"
        count = cache.get(user_key, 0)
        if count >= 5:  # 5 requests per hour
            return JsonResponse({"error": "Rate limit exceeded"}, status=429)
        cache.set(user_key, count+1, timeout=3600)  # 1 hour
        return view_func(request, *args, **kwargs)
    return wrapped_view


def home(request):
    """Render the home page."""
    return render(request, 'home.html')

def user_login(request):
    """Handle user login."""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            auth_login(request, user)  # Use auth_login instead of login
            messages.success(request, 'You have been logged in.')
            return redirect('home')
        else:
            messages.error(request, 'Invalid credentials.')
    return render(request, 'login.html')



@login_required
def dashboard(request):
    """
    Render the dashboard page for authenticated users.
    Store user activity in DynamoDB (AWS Free Tier).
    """
    try:
        user_activities_table.put_item(
            Item={
                'UserId': str(request.user.id),
                'Activity': 'AccessedDashboard',
                'Timestamp': pd.Timestamp.now().isoformat(),
                'UserAgent': request.META.get('HTTP_USER_AGENT', '')
            }
        )
    except ClientError as e:
        logger.error(f"Error logging user activity: {e}")

    return render(request, 'dashboard.html', {'username': request.user.username})
@login_required
@rate_limit
def predict_stock(request):
    """
    Predict stock price (authenticated users only).
    Log predictions in DynamoDB.
    """
    company = request.GET.get('company')
    company_symbol = request.GET.get('symbol')

    # Load model (example assumes S3 or local model loading logic)
    try:
        model = joblib.load('models/stock_price_predictor_model.joblib')
    except Exception as e:
        logger.error(f"Error loading model: {e}")
        return JsonResponse({"error": "Model loading failed."}, status=500)

    # Prepare data for prediction
    data = pd.DataFrame({
        'Close_Lagged': [get_current_closing(company)],
        'Sentiment_Score': [get_current_sentiment(company)],
        'Company': [company_symbol]
    })
    X_test = data[['Close_Lagged', 'Sentiment_Score', 'Company']]
    prediction = model.predict(X_test)

    # Log prediction in DynamoDB
    try:
        predictions_table.put_item(
            Item={
                'UserId': str(request.user.id),
                'PredictionType': 'Stock',
                'Company': company,
                'PredictionValue': str(prediction[0]),
                'Timestamp': pd.Timestamp.now().isoformat()
            }
        )
    except ClientError as e:
        logger.error(f"Error logging prediction: {e}")

    return JsonResponse({"prediction": float(prediction[0])})

@login_required
@rate_limit
def predict_forex(request):
    """
    Predict forex price (authenticated users only).
    Log predictions in DynamoDB.
    """
    forex_pair = request.GET.get('pair')

    # Load model (example assumes S3 or local model loading logic)
    try:
        model = joblib.load(f'models/{forex_pair}.joblib')
    except Exception as e:
        logger.error(f"Error loading model: {e}")
        return JsonResponse({"error": "Model loading failed."}, status=500)

    # Prepare data for prediction
    data = pd.DataFrame({
        'Close': [get_current_closing(forex_pair)],
        'High': [get_current_high(forex_pair)],
        'Low': [get_current_low(forex_pair)],
        'Volume': [get_current_volume(forex_pair)]
    })
    prediction = model.predict(data)

    # Log prediction in DynamoDB
    try:
        predictions_table.put_item(
            Item={
                'UserId': str(request.user.id),
                'PredictionType': 'Forex',
                'ForexPair': forex_pair,
                'PredictionValue': str(prediction[0]),
                'Timestamp': pd.Timestamp.now().isoformat()
            }
        )
    except ClientError as e:
        logger.error(f"Error logging prediction: {e}")

    return JsonResponse({"prediction": float(prediction[0])})

def get_current_closing(company):
    """Fetch current closing price for a company."""
    ticker = yf.Ticker(company)
    data = ticker.history(period="1d")
    return data['Close'].iloc[-1]

# Load environment variables
GNEWS_API_KEY = os.getenv('GNEWS_API_KEY')
GNEWS_BASE_URL = "https://gnews.io/api/v4/search"

def fetch_recent_news(company_name):
    """
    Fetch recent news articles about a company using the GNews API.
    Cache results in DynamoDB to minimize API calls.
    Track daily API usage to stay within Free Tier limits (100 requests/day).
    """
    try:
        # Check if cached news exists and is less than 24 hours old
        response = news_cache_table.get_item(Key={'Company': company_name})
        if 'Item' in response:
            item = response['Item']
            timestamp = datetime.fromisoformat(item['Timestamp'])
            if datetime.now() - timestamp < timedelta(hours=24):
                return item['Articles']
    except ClientError as e:
        print(f"Error accessing DynamoDB: {e}")

    # Check daily API usage counter
    news_counter_key = "gnews_daily_counter"
    count = cache.get(news_counter_key, 0)
    if count >= 100:  # GNews Free Tier limit
        print("Daily GNews API limit reached. Using cached data only.")
        return []

    # Fetch news from GNews API
    try:
        params = {
            'q': company_name,
            'lang': 'en',
            'country': 'US',
            'max': 5,  # Limit to 5 articles per request
            'apikey': GNEWS_API_KEY
        }
        response = requests.get(GNEWS_BASE_URL, params=params)
        if response.status_code == 200:
            data = response.json()
            articles = data.get('articles', [])

            # Cache the result in DynamoDB
            news_cache_table.put_item(
                Item={
                    'Company': company_name,
                    'Articles': articles,
                    'Timestamp': datetime.now().isoformat()
                }
            )

            # Increment daily API usage counter
            cache.set(news_counter_key, count + 1, timeout=86400)  # Reset after 24 hours
            return articles
        else:
            print(f"Error fetching news: {response.status_code}")
            return []
    except Exception as e:
        print(f"Unexpected error in fetching news: {e}")
        return []


def get_current_sentiment(company):
    """
    Fetch sentiment score for a company using AWS Comprehend.
    Cache results in DynamoDB to minimize API calls.
    Track monthly API usage to stay within Free Tier limits (50,000 text units/month).
    """
    try:
        # Check if cached sentiment exists and is less than 1 hour old
        response = sentiment_cache_table.get_item(Key={'Company': company})
        if 'Item' in response:
            item = response['Item']
            timestamp = pd.to_datetime(item['Timestamp'])
            if (pd.Timestamp.now() - timestamp).total_seconds() < 3600:
                return float(item['Score'])
    except ClientError as e:
        print(f"Error accessing DynamoDB: {e}")

    # Check monthly API usage counter
    comprehend_counter_key = "comprehend_monthly_counter"
    count = cache.get(comprehend_counter_key, 0)
    if count >= 45000:  # Leave buffer below 50,000
        print("Monthly AWS Comprehend API limit reached. Using neutral sentiment fallback.")
        return 0.5  # Neutral fallback

    # Fetch recent news
    articles = fetch_recent_news(company)
    if not articles:
        return 0.5  # Neutral fallback

    # Prepare sample text for sentiment analysis
    sample_text = " ".join([article['title'] for article in articles])[:5000]  # Limit to 5,000 characters

    # Perform sentiment analysis using AWS Comprehend
    comprehend = boto3.client('comprehend')
    try:
        response = comprehend.detect_sentiment(Text=sample_text, LanguageCode='en')
        sentiment_map = {'POSITIVE': 0.9, 'NEGATIVE': 0.1, 'NEUTRAL': 0.5, 'MIXED': 0.5}
        sentiment_score = sentiment_map.get(response['Sentiment'], 0.5)

        # Cache the result in DynamoDB
        sentiment_cache_table.put_item(
            Item={
                'Company': company,
                'Score': str(sentiment_score),
                'Timestamp': pd.Timestamp.now().isoformat()
            }
        )

        # Increment monthly API usage counter
        cache.set(comprehend_counter_key, count + len(sample_text), timeout=2592000)  # Reset after 30 days
        return sentiment_score
    except (BotoCoreError, ClientError) as error:
        print(f"AWS Comprehend error: {error}")
        return 0.5  # Fallback neutral value
    except Exception as e:
        print(f"Unexpected error in sentiment analysis: {e}")
        return 0.5  # Fallback neutral value


def register(request):
    """Handle user registration."""
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        if password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'register.html')

        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
            return render(request, 'register.html')

        # Create a new user
        user = User.objects.create_user(username=username, email=email, password=password)
        user.save()
        messages.success(request, 'Registration successful! Please login.')
        return redirect('login')


    return render(request, 'register.html')


@login_required
def logout(request):
    """Handle user logout."""
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('home')


@login_required
def user_profile(request):
    """Display user profile with activity history."""
    try:
        # Get user activities from SQLite
        activities = UserActivity.objects.filter(user=request.user).order_by('-timestamp')[:10]
    except Exception as e:
        logger.error(f"Error fetching user activities: {e}")
        activities = []

    return render(request, 'profile.html', {
        'user': request.user,
        'activities': activities
    })
# app/views.py
import os

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
from django.contrib.auth import logout as auth_logout

from app.models import UserActivity, Prediction

# In app/views.py
from django.http import HttpResponse


def health_check(request):
    return HttpResponse("OK", status=200)


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
    0: {'name': 'AUD/USD ASK', 'model_file': 'AUD-USD-ASK.joblib', 'symbol': 'AUDUSD=X'},
    1: {'name': 'AUD/USD BID', 'model_file': 'AUD-USD-BID.joblib', 'symbol': 'AUDUSD=X'},
    2: {'name': 'EUR/USD ASK', 'model_file': 'EUR-USD-ASK.joblib', 'symbol': 'EURUSD=X'},
    3: {'name': 'EUR/USD BID', 'model_file': 'EUR-USD-BID.joblib', 'symbol': 'EURUSD=X'},
    4: {'name': 'GBP/USD ASK', 'model_file': 'GBP-USD-ASK.joblib', 'symbol': 'GBPUSD=X'},
    5: {'name': 'GBP/USD BID', 'model_file': 'GBP-USD-BID.joblib', 'symbol': 'GBPUSD=X'},
    6: {'name': 'NZD/USD ASK', 'model_file': 'NZD-USD-ASK.joblib', 'symbol': 'NZDUSD=X'},
    7: {'name': 'NZD/USD BID', 'model_file': 'NZD-USD-BID.joblib', 'symbol': 'NZDUSD=X'},
    8: {'name': 'USD/CAD ASK', 'model_file': 'USD-CAD-ASK.joblib', 'symbol': 'USDCAD=X'},
    9: {'name': 'USD/CAD BID', 'model_file': 'USD-CAD-BID.joblib', 'symbol': 'USDCAD=X'},
    10: {'name': 'USD/CHF ASK', 'model_file': 'USD-CHF-ASK.joblib', 'symbol': 'USDCHF=X'},
    11: {'name': 'USD/CHF BID', 'model_file': 'USD-CHF-BID.joblib', 'symbol': 'USDCHF=X'},
    12: {'name': 'USD/JPY ASK', 'model_file': 'USD-JPY-ASK.joblib', 'symbol': 'USDJPY=X'},
    13: {'name': 'USD/JPY BID', 'model_file': 'USD-JPY-BID.joblib', 'symbol': 'USDJPY=X'},
    14: {'name': 'XAG/USD ASK', 'model_file': 'XAG-USD-ASK.joblib', 'symbol': 'XAGUSD=X'},
    15: {'name': 'XAG/USD BID', 'model_file': 'XAG-USD-BID.joblib', 'symbol': 'XAGUSD=X'},
}


def load_model_from_s3(bucket_name, model_key):
    """
    Downloads a model file from S3 and loads it using joblib.
    """
    # Initialize the S3 client
    s3 = boto3.client('s3')

    # Define the local path for the downloaded model
    local_path = os.path.join('/tmp', model_key.split('/')[-1])

    # Ensure the directory exists
    os.makedirs(os.path.dirname(local_path), exist_ok=True)

    # Download the model file if it doesn't already exist locally
    if not os.path.exists(local_path):
        logger.info(f"Downloading model from S3: {model_key}")
        try:
            s3.download_file(bucket_name, model_key, local_path)
        except Exception as e:
            logger.error(f"Error downloading model from S3: {e}")
            raise
    else:
        logger.info(f"Model already exists locally: {local_path}")

    # Load the model using joblib
    try:
        model = joblib.load(local_path)
        return model
    except Exception as e:
        logger.error(f"Error loading model with joblib: {e}")
        raise


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
        cache.set(user_key, count + 1, timeout=3600)  # 1 hour
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
    """Render the dashboard page for authenticated users."""
    try:
        # Store user activity in DynamoDB
        user_activities_table.put_item(
            Item={
                'UserId': str(request.user.id),
                'Activity': 'AccessedDashboard',
                'Timestamp': datetime.now().isoformat(),
                'UserAgent': request.META.get('HTTP_USER_AGENT', '')
            }
        )
    except ClientError as e:
        logger.error(f"Error logging user activity: {e}")

    return render(request, 'dashboard.html', {'username': request.user.username})

# Load environment variables
bucket_name = 'stock-forex-app'  # Replace with your S3 bucket name

@login_required
@rate_limit
def predict_stock(request):
    # Initialize variables for rendering
    prediction = None
    error = None

    if request.method == "GET":
        # Render the form with company mapping for selection
        return render(request, "predict_stock.html", {"company_mapping": company_mapping})

    elif request.method == "POST":
        try:
            # Extract company symbol from POST request
            company_symbol = request.POST.get("company_symbol")
            if not company_symbol:
                error = "Missing company_symbol"
                return render(request, "predict_stock.html", {"company_mapping": company_mapping, "error": error})

            # Validate the symbol against the mapping
            try:
                company_symbol = int(company_symbol)
                if company_symbol not in company_mapping:
                    error = "Invalid company_symbol."
                    return render(request, "predict_stock.html", {"company_mapping": company_mapping, "error": error})
            except ValueError:
                error = "Invalid company_symbol. It should be an integer."
                return render(request, "predict_stock.html", {"company_mapping": company_mapping, "error": error})

            company = company_mapping[company_symbol]

            # Fetch stock data (closing price)
            closing_price = get_current_closing(company)
            if closing_price is None:
                error = "Failed to fetch stock data."
                return render(request, "predict_stock.html", {"company_mapping": company_mapping, "error": error})

            # Load model from S3 or fallback to local storage
            try:
                bucket_name = 'stock-forex-app'  # Replace with your S3 bucket name
                model_key = 'models/stock_price_predictor_model.joblib'
                s3_client = boto3.client('s3')
                s3_client.download_file(bucket_name, model_key, '/tmp/stock_price_predictor_model.joblib')
                model = joblib.load('/tmp/stock_price_predictor_model.joblib')
            except Exception as e:
                logger.error(f"Error loading model: {e}")
                error = "Model loading failed."
                return render(request, "predict_stock.html", {"company_mapping": company_mapping, "error": error})

            # Prepare data for prediction
            try:
                data = pd.DataFrame({
                    'Close_Lagged': [closing_price],
                    'Sentiment_Score': [get_current_sentiment(company)],
                    'Company': [company_symbol],
                })
                X_test = data[['Close_Lagged', 'Sentiment_Score', 'Company']]
                prediction = model.predict(X_test)[0]
            except Exception as e:
                logger.error(f"Error during prediction: {e}")
                error = "Prediction failed."
                return render(request, "predict_stock.html", {"company_mapping": company_mapping, "error": error})

            # Log prediction in DynamoDB
            try:
                dynamodb = boto3.resource('dynamodb')
                table = dynamodb.Table('Predictions')
                table.put_item(Item={
                    'UserId': str(request.user.id),
                    'PredictionType': 'Stock',
                    'Company': company,
                    'PredictionValue': str(prediction),
                    'Timestamp': pd.Timestamp.now().isoformat(),
                })
            except ClientError as e:
                logger.error(f"Error logging prediction: {e}")

            # Render the template with the prediction result
            return render(request, "predict_stock.html", {
                "company_mapping": company_mapping,
                "prediction": prediction,
            })

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            error = "An unexpected error occurred."
            return JsonResponse({"error": "An unexpected error occurred."}, status=500)


@rate_limit
@login_required
def predict_forex(request):
    # Initialize variables for rendering
    prediction = None
    error = None

    if request.method == "GET":
        # Render the form with forex mapping for selection
        return render(request, "predict_forex.html", {"forex_mapping": forex_mapping})

    elif request.method == "POST":
        try:
            # Extract forex symbol from POST request
            forex_symbol = request.POST.get("forex_symbol")
            if not forex_symbol:
                error = "Missing forex_symbol"
                return render(request, "predict_forex.html", {"forex_mapping": forex_mapping, "error": error})

            # Validate the symbol against the mapping
            try:
                forex_symbol = int(forex_symbol)
                if forex_symbol not in forex_mapping:
                    error = "Invalid forex_symbol."
                    return render(request, "predict_forex.html", {"forex_mapping": forex_mapping, "error": error})
            except ValueError:
                error = "Invalid forex_symbol. It should be an integer."
                return render(request, "predict_forex.html", {"forex_mapping": forex_mapping, "error": error})

            # Get the forex pair details
            forex_pair_details = forex_mapping[forex_symbol]
            forex_pair_name = forex_pair_details['name']  # User-friendly name
            model_file = forex_pair_details['model_file']  # Actual .joblib filename
            symbol = forex_pair_details['symbol']  # Correct symbol for yfinance

            # Load model from S3 or fallback to local storage
            bucket_name = 'stock-forex-app'  # Replace with your S3 bucket name
            model_key = f'models/{model_file}'  # Path to the model in S3
            try:
                s3_client = boto3.client('s3')
                s3_client.download_file(bucket_name, model_key, f'/tmp/{model_file}')
                model = joblib.load(f'/tmp/{model_file}')
            except Exception as e:
                logger.error(f"Error loading model: {e}")
                error = "Model loading failed."
                return render(request, "predict_forex.html", {"forex_mapping": forex_mapping, "error": error})

            # Prepare data for prediction
            try:
                closing_price = get_current_closing(symbol)
                high_price = get_current_high(symbol)
                low_price = get_current_low(symbol)
                volume = get_current_volume(symbol)

                if closing_price is None or high_price is None or low_price is None or volume is None:
                    error = "Failed to fetch forex data."
                    return render(request, "predict_forex.html", {"forex_mapping": forex_mapping, "error": error})

                data = pd.DataFrame({
                    'Close': [closing_price],
                    'High': [high_price],
                    'Low': [low_price],
                    'Volume': [volume]
                })
                prediction = model.predict(data)[0]
            except Exception as e:
                logger.error(f"Error during prediction: {e}")
                error = "Prediction failed."
                return render(request, "predict_forex.html", {"forex_mapping": forex_mapping, "error": error})

            # Log prediction in DynamoDB
            try:
                dynamodb = boto3.resource('dynamodb')
                table = dynamodb.Table('Predictions')
                table.put_item(Item={
                    'UserId': str(request.user.id),
                    'PredictionType': 'Forex',
                    'ForexPair': forex_pair_name,  # Use the user-friendly name
                    'PredictionValue': str(prediction),
                    'Timestamp': pd.Timestamp.now().isoformat()
                })
            except ClientError as e:
                logger.error(f"Error logging prediction: {e}")

            # Render the template with the prediction result
            return render(request, "predict_forex.html", {
                "forex_mapping": forex_mapping,
                "prediction": prediction,
                "forex_pair_name": forex_pair_name,  # Pass the user-friendly name to the frontend
            })

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            error = "An unexpected error occurred."
            return render(request, "predict_forex.html", {"forex_mapping": forex_mapping, "error": error})

def get_current_closing(symbol):
    """
    Fetch current closing price for a stock or forex pair.
    """
    try:
        ticker = yf.Ticker(symbol)
        data = ticker.history(period="1d")
        if data.empty:
            raise ValueError(f"No data found for symbol: {symbol}")
        return data['Close'].iloc[-1]
    except Exception as e:
        logger.error(f"Error fetching closing price for {symbol}: {e}")
        return None

def get_current_high(symbol):
    """
    Fetch current high price for a stock or forex pair.
    """
    try:
        ticker = yf.Ticker(symbol)
        data = ticker.history(period="1d")
        if data.empty:
            raise ValueError(f"No data found for symbol: {symbol}")
        return data['High'].iloc[-1]
    except Exception as e:
        logger.error(f"Error fetching high price for {symbol}: {e}")
        return None

def get_current_low(symbol):
    """
    Fetch current low price for a stock or forex pair.
    """
    try:
        ticker = yf.Ticker(symbol)
        data = ticker.history(period="1d")
        if data.empty:
            raise ValueError(f"No data found for symbol: {symbol}")
        return data['Low'].iloc[-1]
    except Exception as e:
        logger.error(f"Error fetching low price for {symbol}: {e}")
        return None

def get_current_volume(symbol):
    """
    Fetch current trading volume for a stock or forex pair.
    """
    try:
        ticker = yf.Ticker(symbol)
        data = ticker.history(period="1d")
        if data.empty:
            raise ValueError(f"No data found for symbol: {symbol}")
        return data['Volume'].iloc[-1]
    except Exception as e:
        logger.error(f"Error fetching volume for {symbol}: {e}")
        return None

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


def custom_logout(request):
    """
    Handle user logout with custom logic.
    """
    try:
        # Log logout event in DynamoDB
        if request.user.is_authenticated:
            dynamodb = boto3.resource('dynamodb')
            table = dynamodb.Table('UserLogins')
            table.put_item(Item={
                'UserId': str(request.user.id),
                'LogoutTime': str(pd.Timestamp.now()),
                'IPAddress': request.META.get('REMOTE_ADDR', '')
            })

        # Perform logout using Django's built-in logout function
        auth_logout(request)

        # Add success message
        messages.success(request, 'You have been logged out.')

    except Exception as e:
        # Log any errors during logout
        logger.error(f"Error during logout: {e}")
        messages.error(request, 'An error occurred while logging out.')

    # Always redirect to the home page
    return redirect('home')


@login_required
def user_profile(request):
    """
    Display user profile with activity history.
    """
    try:
        # Fetch user activities from DynamoDB
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table('UserActivities')
        response = table.query(
            KeyConditionExpression='UserId = :uid',
            ExpressionAttributeValues={':uid': str(request.user.id)},
            Limit=10,  # Show the last 10 activities
            ScanIndexForward=False  # Sort by most recent first
        )
        activities = response.get('Items', [])
    except ClientError as e:
        logger.error(f"Error fetching user activities: {e}")
        activities = []

    return render(request, 'profile.html', {
        'user': request.user,
        'activities': activities
    })

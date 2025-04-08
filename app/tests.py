from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from app.models import UserActivity, Prediction
import boto3
from moto import mock_aws  # This mocks all AWS services
import os

from app.views import create_dynamodb_user, get_dynamodb_user


# tests.py
@mock_aws
class BaseTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

        # Create all required tables with proper configurations
        tables = [
            {
                'TableName': 'Users',
                'KeySchema': [{'AttributeName': 'username', 'KeyType': 'HASH'}],
                'AttributeDefinitions': [{'AttributeName': 'username', 'AttributeType': 'S'}],
                'ProvisionedThroughput': {'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
            },
            {
                'TableName': 'UserActivities',
                'KeySchema': [
                    {'AttributeName': 'UserId', 'KeyType': 'HASH'},
                    {'AttributeName': 'Timestamp', 'KeyType': 'RANGE'}
                ],
                'AttributeDefinitions': [
                    {'AttributeName': 'UserId', 'AttributeType': 'S'},
                    {'AttributeName': 'Timestamp', 'AttributeType': 'S'}
                ],
                'ProvisionedThroughput': {'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
            },
            {
                'TableName': 'Predictions',
                'KeySchema': [
                    {'AttributeName': 'UserId', 'KeyType': 'HASH'},
                    {'AttributeName': 'Timestamp', 'KeyType': 'RANGE'}
                ],
                'AttributeDefinitions': [
                    {'AttributeName': 'UserId', 'AttributeType': 'S'},
                    {'AttributeName': 'Timestamp', 'AttributeType': 'S'}
                ],
                'ProvisionedThroughput': {'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
            },
            {
                'TableName': 'Sessions',
                'KeySchema': [{'AttributeName': 'session_key', 'KeyType': 'HASH'}],
                'AttributeDefinitions': [{'AttributeName': 'session_key', 'AttributeType': 'S'}],
                'ProvisionedThroughput': {'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
            }
        ]

        for table_config in tables:
            try:
                table = self.dynamodb.create_table(**table_config)
                table.wait_until_exists()
            except Exception as e:
                if "ResourceInUseException" not in str(e):
                    raise



# tests.py
@mock_aws
class BasicViewTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        # Pre-populate DynamoDB with test user
        create_dynamodb_user('testuser', 'testuser@example.com', 'testpass123')

    def test_valid_login(self):
        response = self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'testpass123'
        })
        self.assertRedirects(response, reverse('home'))

    def test_invalid_login(self):
        response = self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'wrongpass'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid credentials')


    def test_home_page(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'home.html')

    def test_login_page(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'login.html')

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse('dashboard'))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('dashboard')}")

    def test_dashboard_authenticated(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard.html')


@mock_aws
class DynamoDBTests(TestCase):
    def setUp(self):
        self.dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        self.table_name = 'UserActivities'
        self.table = self.dynamodb.create_table(
            TableName=self.table_name,
            KeySchema=[
                {'AttributeName': 'UserId', 'KeyType': 'HASH'},
                {'AttributeName': 'Timestamp', 'KeyType': 'RANGE'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'UserId', 'AttributeType': 'S'},
                {'AttributeName': 'Timestamp', 'AttributeType': 'S'}
            ],
            ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
        )
        self.table.wait_until_exists()

    def test_user_activity_logging(self):
        from app.views import user_activities_table

        # Mock the table reference
        user_activities_table = self.table

        # Test activity logging
        activity_item = {
            'UserId': 'testuser123',
            'Activity': 'TestActivity',
            'Timestamp': '2023-01-01T00:00:00',
            'UserAgent': 'TestAgent'
        }

        user_activities_table.put_item(Item=activity_item)

        # Verify the item was inserted
        response = user_activities_table.get_item(
            Key={
                'UserId': 'testuser123',
                'Timestamp': '2023-01-01T00:00:00'
            }
        )
        self.assertEqual(response['Item'], activity_item)


# tests.py
@mock_aws
class PredictionModelTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        create_dynamodb_user('testuser', 'testuser@example.com', 'testpass123')
        self.client.login(username='testuser', password='testpass123')


    def test_stock_prediction_view(self):
        response = self.client.get(reverse('predict_stock'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'predict_stock.html')

    def test_forex_prediction_view(self):
        response = self.client.get(reverse('predict_forex'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'predict_forex.html')


# tests.py
@mock_aws
class RegistrationTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()

    def test_registration_page(self):
        response = self.client.get(reverse('register'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'register.html')

    def test_valid_registration(self):
        response = self.client.post(reverse('register'), {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'newpass123',
            'confirm_password': 'newpass123'
        })
        self.assertRedirects(response, reverse('login'))
        self.assertTrue(User.objects.filter(username='newuser').exists())
        # Verify DynamoDB entry
        user = get_dynamodb_user('newuser')
        self.assertIsNotNone(user)
        self.assertEqual(user['email'], 'newuser@example.com')

    def test_invalid_registration(self):
        response = self.client.post(reverse('register'), {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'newpass123',
            'confirm_password': 'differentpass'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Passwords do not match')
        self.assertFalse(User.objects.filter(username='newuser').exists())
from django.test import TestCase, Client
from django.urls import reverse
from moto import mock_aws
import boto3
from app.views import create_dynamodb_user, get_dynamodb_user
import time  # Import time module

@mock_aws
class BaseTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

        # Create required DynamoDB tables
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
            }
        ]

        for table_config in tables:
            table = self.dynamodb.create_table(**table_config)
            table.wait_until_exists()  # Wait until the table is fully created

        # Create a test user in DynamoDB
        create_dynamodb_user('testuser', 'testuser@example.com', 'testpass123')


@mock_aws
class BasicViewTests(BaseTestCase):
    def test_valid_login(self):
        response = self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'testpass123'
        })
        self.assertRedirects(response, reverse('home'))
        # Verify session is populated
        self.assertIn('user', self.client.session)
        self.assertEqual(self.client.session['user']['username'], 'testuser')

    def test_invalid_login(self):
        response = self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'wrongpass'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid credentials')
        # Verify session is not populated
        self.assertNotIn('user', self.client.session)

    def test_home_page(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'home.html')

    def test_login_page(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'login.html')

    def test_dashboard_requires_login(self):
        """
        Test that unauthenticated users are redirected to the login page with the 'next' parameter.
        """
        response = self.client.get(reverse('dashboard'))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('dashboard')}")

    def test_dashboard_authenticated(self):
        # Simulate login by populating the session
        session = self.client.session
        session['user'] = {
            'username': 'testuser',
            'is_authenticated': True
        }
        session.save()

        # Access the dashboard
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)


@mock_aws
class RegistrationTests(BaseTestCase):
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

        # Verify user was not created in DynamoDB
        user = get_dynamodb_user('newuser')
        self.assertIsNone(user)
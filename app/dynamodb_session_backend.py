# app/dynamodb_session_backend.py
import boto3
from botocore.exceptions import ClientError
from datetime import datetime, timedelta
from django.conf import settings
from django.contrib.sessions.backends.base import SessionBase, CreateError
import uuid


class DynamoDBSessionStore(SessionBase):
    def __init__(self, session_key=None):
        super().__init__(session_key)
        self.dynamodb = boto3.resource(
            'dynamodb',
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )
        self.table = self.dynamodb.Table(settings.DYNAMODB_SESSIONS_TABLE_NAME)
        # Ensure session_key is always set
        if not self._session_key:
            self._session_key = str(uuid.uuid4())

    def load(self):
        try:
            response = self.table.get_item(Key={'session_key': self.session_key})
            if 'Item' in response:
                item = response['Item']
                expires_at = datetime.fromisoformat(item['expires_at'])
                if expires_at > datetime.now():
                    return self.decode(item['data'])
            return {}
        except ClientError as e:
            print(f"Error loading session: {e}")
            return {}

    def exists(self, session_key):
        try:
            response = self.table.get_item(Key={'session_key': session_key})
            return 'Item' in response
        except ClientError:
            return False

    def create(self):
        self._session_key = str(uuid.uuid4())
        self.modified = True
        self.save(must_create=True)
        return

    def save(self, must_create=False):
        # Double-check session_key is set
        if not self._session_key:
            self._session_key = str(uuid.uuid4())

        data = {
            'session_key': self._session_key,  # Use _session_key directly
            'data': self.encode(self._get_session(no_load=must_create)),
            'expires_at': (datetime.now() + timedelta(seconds=settings.SESSION_COOKIE_AGE)).isoformat()
        }

        try:
            if must_create:
                self.table.put_item(
                    Item=data,
                    ConditionExpression='attribute_not_exists(session_key)'
                )
            else:
                self.table.put_item(Item=data)
        except ClientError as e:
            print(f"Error saving session: {e}")
            raise CreateError(f"Failed to save session: {str(e)}")

    def delete(self, session_key=None):
        try:
            key = session_key if session_key else self._session_key
            if key:
                self.table.delete_item(Key={'session_key': key})
        except ClientError as e:
            print(f"Error deleting session: {e}")

    @property
    def session_key(self):
        return self._session_key


class SessionStore(DynamoDBSessionStore):
    pass
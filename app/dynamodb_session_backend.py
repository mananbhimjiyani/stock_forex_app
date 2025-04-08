import sys

import boto3
from botocore.exceptions import ClientError, BotoCoreError
from datetime import datetime, timedelta
from django.conf import settings
from django.contrib.sessions.backends.base import SessionBase, CreateError
import uuid
import logging

logger = logging.getLogger(__name__)


class DynamoDBSessionStore(SessionBase):
    """
    A DynamoDB-backed session store with improved error handling and test support
    """

    def __init__(self, session_key=None):
        super().__init__(session_key)
        self._table = None  # Will be initialized lazily
        self._session_key = session_key or str(uuid.uuid4())

        # Configure AWS client
        self.dynamodb = boto3.resource(
            'dynamodb',
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )

        # For testing, ensure table exists
        if 'test' in sys.argv:
            self._ensure_table_exists()

    @property
    def table(self):
        """Lazy table initialization with existence check"""
        if self._table is None:
            self._table = self.dynamodb.Table(settings.DYNAMODB_SESSIONS_TABLE_NAME)
            try:
                self._table.table_status  # Check if table exists
            except (ClientError, BotoCoreError) as e:
                logger.error(f"Session table access error: {e}")
                raise CreateError(f"Session table not accessible: {str(e)}")
        return self._table

    def _ensure_table_exists(self):
        """Ensure the session table exists (primarily for testing)"""
        try:
            existing_tables = self.dynamodb.meta.client.list_tables()['TableNames']
            if settings.DYNAMODB_SESSIONS_TABLE_NAME not in existing_tables:
                self.dynamodb.create_table(
                    TableName=settings.DYNAMODB_SESSIONS_TABLE_NAME,
                    KeySchema=[{'AttributeName': 'session_key', 'KeyType': 'HASH'}],
                    AttributeDefinitions=[{'AttributeName': 'session_key', 'AttributeType': 'S'}],
                    BillingMode='PAY_PER_REQUEST'
                )
                logger.info(f"Created session table {settings.DYNAMODB_SESSIONS_TABLE_NAME}")
        except (ClientError, BotoCoreError) as e:
            logger.error(f"Error ensuring table exists: {e}")
            raise CreateError(f"Failed to create session table: {str(e)}")

    def load(self):
        """Load session data from DynamoDB"""
        try:
            response = self.table.get_item(
                Key={'session_key': self._session_key},
                ConsistentRead=True  # Ensure we get the latest data
            )
            if 'Item' in response:
                item = response['Item']
                expires_at = datetime.fromisoformat(item['expires_at'])
                if expires_at > datetime.now():
                    return self.decode(item['data'])
                # Auto-delete expired sessions
                self.delete(self._session_key)
            return {}
        except (ClientError, BotoCoreError) as e:
            logger.error(f"Error loading session {self._session_key}: {e}")
            return {}

    def exists(self, session_key):
        """Check if a session exists"""
        try:
            response = self.table.get_item(
                Key={'session_key': session_key},
                ProjectionExpression='session_key'  # Only fetch the key to minimize data transfer
            )
            return 'Item' in response
        except (ClientError, BotoCoreError) as e:
            logger.error(f"Error checking session existence {session_key}: {e}")
            return False

    def create(self):
        """Create a new session"""
        self._session_key = str(uuid.uuid4())
        self.modified = True
        self.save(must_create=True)
        return self._session_key

    def save(self, must_create=False):
        """Save session data to DynamoDB"""
        if not self._session_key:
            self._session_key = str(uuid.uuid4())

        session_data = self._get_session(no_load=must_create)
        data = {
            'session_key': self._session_key,
            'data': self.encode(session_data),
            'expires_at': (datetime.now() + timedelta(seconds=self.get_expiry_age())).isoformat(),
            'last_modified': datetime.now().isoformat()
        }

        try:
            if must_create:
                self.table.put_item(
                    Item=data,
                    ConditionExpression='attribute_not_exists(session_key)'
                )
            else:
                self.table.put_item(Item=data)
        except (ClientError, BotoCoreError) as e:
            logger.error(f"Error saving session {self._session_key}: {e}")
            raise CreateError(f"Failed to save session: {str(e)}")

    def delete(self, session_key=None):
        """Delete a session"""
        key = session_key if session_key else self._session_key
        if not key:
            return

        try:
            self.table.delete_item(Key={'session_key': key})
        except (ClientError, BotoCoreError) as e:
            logger.error(f"Error deleting session {key}: {e}")
            # Don't raise exception for delete failures to avoid breaking logout flow

    def clear(self):
        """Clear all session data"""
        self._session_cache = {}
        self.modified = True
        self.save()

    @property
    def session_key(self):
        return self._session_key


class SessionStore(DynamoDBSessionStore):
    """Compatibility class for Django's session backend system"""
    pass
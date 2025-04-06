import boto3
from botocore.exceptions import ClientError
from datetime import datetime, timedelta
from django.conf import settings
from django.contrib.sessions.backends.base import SessionBase, CreateError

# Initialize DynamoDB resource
dynamodb = boto3.resource(
    'dynamodb',
    region_name=settings.AWS_REGION,
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
)
table = dynamodb.Table(settings.DYNAMODB_SESSIONS_TABLE_NAME)


class DynamoDBSessionStore(SessionBase):
    def __init__(self, session_key=None):
        super().__init__(session_key)

    def load(self):
        try:
            response = table.get_item(Key={'session_key': self.session_key})
            if 'Item' in response:
                item = response['Item']
                expires_at = datetime.fromisoformat(item['expires_at'])
                if expires_at > datetime.now():
                    return self.decode(item['data'])
        except (ClientError, ValueError) as e:
            if isinstance(e, ClientError):
                print(f"Error loading session: {e}")
            return {}
        return {}

    def exists(self, session_key):
        try:
            response = table.get_item(Key={'session_key': session_key})
            return 'Item' in response
        except ClientError as e:
            print(f"Error checking session existence: {e}")
            return False

    def create(self):
        while True:
            self._session_key = self._get_new_session_key()
            try:
                self.save(must_create=True)
            except CreateError:
                continue
            self.modified = True
            return

    def save(self, must_create=False):
        try:
            expires_at = datetime.now() + timedelta(seconds=settings.SESSION_COOKIE_AGE)
            item = {
                'session_key': self.session_key,
                'data': self.encode(self._get_session(no_load=must_create)),
                'expires_at': expires_at.isoformat()
            }
            if must_create:
                table.put_item(Item=item, ConditionExpression='attribute_not_exists(session_key)')
            else:
                table.put_item(Item=item)
        except ClientError as e:
            print(f"Error saving session: {e}")
            raise CreateError

    def delete(self, session_key=None):
        try:
            key = session_key or self.session_key
            table.delete_item(Key={'session_key': key})
        except ClientError as e:
            print(f"Error deleting session: {e}")


# Define the SessionStore class
class SessionStore(DynamoDBSessionStore):
    pass
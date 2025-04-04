from django.db import models
from django.contrib.auth.models import User

class UserActivity(models.Model):
    """Model to store user activity logs."""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    activity = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    user_agent = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} - {self.activity} at {self.timestamp}"


class Prediction(models.Model):
    """Model to store predictions."""
    PREDICTION_TYPE_CHOICES = [
        ('Stock', 'Stock'),
        ('Forex', 'Forex'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    prediction_type = models.CharField(max_length=10, choices=PREDICTION_TYPE_CHOICES)
    company = models.CharField(max_length=50, blank=True, null=True)
    forex_pair = models.CharField(max_length=50, blank=True, null=True)
    prediction_value = models.FloatField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.prediction_type} at {self.timestamp}"


class NewsCache(models.Model):
    """Model to cache news articles."""
    company = models.CharField(max_length=50, unique=True)
    articles = models.JSONField()  # Store articles as JSON
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"News for {self.company} cached at {self.timestamp}"


class SentimentCache(models.Model):
    """Model to cache sentiment scores."""
    company = models.CharField(max_length=50, unique=True)
    score = models.FloatField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Sentiment for {self.company}: {self.score} at {self.timestamp}"
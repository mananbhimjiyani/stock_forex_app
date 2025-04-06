# app/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('predict_stock/', views.predict_stock, name='predict_stock'),
    path('predict_forex/', views.predict_forex, name='predict_forex'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.custom_logout, name='logout'),
    path('register/', views.register, name='register'),
    path('health/', views.health_check, name='health_check'),
    path('profile/', views.user_profile, name='user_profile'),
]
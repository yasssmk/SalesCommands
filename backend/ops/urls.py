# backend/ops/urls.py

"""
Ops App URLs - Test & Monitoring Endpoints

Routes for development/testing utilities and health monitoring.
"""

from django.urls import path
from .views import (
    SleepView,
    Error500View,
    Error404View,
    HealthCheckView
)

app_name = 'ops'

urlpatterns = [
    # =========================================================================
    # TIMEOUT TESTING
    # =========================================================================
    
    # Sleep endpoint - both GET and POST for testing different profiles
    path('sleep/<int:seconds>/', SleepView.as_view(), name='sleep'),
    
    # =========================================================================
    # ERROR SIMULATION
    # =========================================================================
    
    # Trigger specific errors for frontend testing
    path('error-500/', Error500View.as_view(), name='error-500'),
    path('error-404/', Error404View.as_view(), name='error-404'),
    
    # =========================================================================
    # HEALTH & MONITORING
    # =========================================================================
    
    # Health check with Redis status
    path('health/', HealthCheckView.as_view(), name='health'),
]
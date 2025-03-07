from django.urls import path
from .views import ContactAPIView, ContactChoicesView

urlpatterns = [
    # Base endpoints
    path('', ContactAPIView.as_view(), name='contact-list'),
    path('<int:pk>/', ContactAPIView.as_view(), name='contact-detail'),
    
    # Signal-related endpoints
    path('<int:pk>/signals/', ContactAPIView.as_view(), name='contact-signals'),
    path('<int:pk>/field-signals/', ContactAPIView.as_view(), name='contact-field-signals'),
    
    # Choice endpoints
    path('choices/', ContactChoicesView.as_view(), name='contact-choices'),
]
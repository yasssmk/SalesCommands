# apps/signals/urls.py

from django.urls import path
from .views.qualification_signal_view import QualificationSignalView
from .views.tech_stack_signal_view import TechStackSignalView
from .views.profile_signal_view import ProfileSignalView

urlpatterns = [
    # Qualification Signal URLs
    path('qualification/', QualificationSignalView.as_view(), name='qualification-list'),
    path('qualification/<int:pk>/', QualificationSignalView.as_view(), name='qualification-detail'),
    path('qualification/<int:pk>/approve/', QualificationSignalView.as_view(), name='qualification-approve'),
    path('qualification/<int:pk>/reject/', QualificationSignalView.as_view(), name='qualification-reject'),
    path('qualification/by-account/', QualificationSignalView.as_view(), name='qualification-by-account'),
    path('qualification/bulk/', QualificationSignalView.as_view(), name='qualification-bulk'),

    # Tech Stack Signal URLs
    path('tech-stack/', TechStackSignalView.as_view(), name='tech-stack-list'),
    path('tech-stack/<int:pk>/', TechStackSignalView.as_view(), name='tech-stack-detail'),
    path('tech-stack/<int:pk>/approve/', TechStackSignalView.as_view(), name='tech-stack-approve'),
    path('tech-stack/<int:pk>/reject/', TechStackSignalView.as_view(), name='tech-stack-reject'),
    path('tech-stack/by-tech-stack/', TechStackSignalView.as_view(), name='tech-stack-by-tech'),
    path('tech-stack/account-tech-evaluation/', TechStackSignalView.as_view(), name='account-tech-evaluation'),
    path('tech-stack/bulk/', TechStackSignalView.as_view(), name='tech-stack-bulk'),

    # Profile Signal URLs
    path('profile/', ProfileSignalView.as_view(), name='profile-list'),
    path('profile/<int:pk>/', ProfileSignalView.as_view(), name='profile-detail'),
    path('profile/<int:pk>/approve/', ProfileSignalView.as_view(), name='profile-approve'),
    path('profile/<int:pk>/reject/', ProfileSignalView.as_view(), name='profile-reject'),
    path('profile/account-profile/', ProfileSignalView.as_view(), name='account-profile'),
    path('profile/bulk/', ProfileSignalView.as_view(), name='profile-bulk'),
    
    # Common signal actions
    path('<int:pk>/confirm/', QualificationSignalView.as_view(), name='signal-confirm'),
    path('<int:pk>/merge/', QualificationSignalView.as_view(), name='signal-merge'),
]
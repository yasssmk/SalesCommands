from django.urls import path
from .views import AccountAPIView, AccountChoicesView, ContactAPIView, ContactChoicesView, AccountProductRelationshipView, TechRelationshipView, BuyingProcessStepView


urlpatterns = [
    
    #Accounts
    path('', AccountAPIView.as_view(), name='account-list'),  # For GET and POST requests
    path('<int:pk>/', AccountAPIView.as_view(), name='account-detail'),  # For PUT and DELETE by ID 
    path('account-types/', AccountChoicesView.as_view(), name='account-types'),  # For GET request to retrieve account types
    
    path('<int:pk>/signals/', AccountAPIView.as_view(), name='account-signals'),
    path('<int:pk>/field-signals/', AccountAPIView.as_view(), name='account-field-signals'),
    path('<int:pk>/hierarchy/', AccountAPIView.as_view(), name='account-hierarchy'),

    #Contacts
    path('contacts/', ContactAPIView.as_view(), name='contact-list'),
    path('contacts/<int:pk>/', ContactAPIView.as_view(), name='contact-detail'),
    
    # Signal-related endpoints
    path('contacts/<int:pk>/signals/', ContactAPIView.as_view(), name='contact-signals'),
    path('contacts/<int:pk>/field-signals/', ContactAPIView.as_view(), name='contact-field-signals'),
    
    # Choice endpoints
    path('contacts/choices/', ContactChoicesView.as_view(), name='contact-choices'),

    # Buying Process Steps
    path('buying-process-steps/', BuyingProcessStepView.as_view(), name='buying-process-step-list'),
    path('buying-process-steps/<int:pk>/', BuyingProcessStepView.as_view(), name='buying-process-step-detail'),
    path('buying-process-steps/account/<int:account_id>/', BuyingProcessStepView.as_view(), name='buying-process-steps-by-account'),
    path('buying-process-steps/<int:pk>/position/', BuyingProcessStepView.as_view(), name='buying-process-step-position'),
    path('buying-process-steps/<int:pk>/contacts/', BuyingProcessStepView.as_view(), name='buying-process-step-contacts'),

    #APR

    path('apr/', AccountProductRelationshipView.as_view(), name='list'),  # GET (list) and POST
    path('apr/<int:pk>/', AccountProductRelationshipView.as_view(), name='detail'),  # GET, PUT, PATCH, DELETE for specific instance
    
    # Analysis endpoints
    path('apr/<int:pk>/analyze/', AccountProductRelationshipView.as_view(), name='apd_analyze'),
    path('apr/<int:pk>/refresh-analysis/', AccountProductRelationshipView.as_view(), name='apd_refresh_analysis'),
    path('apr/<int:pk>/analysis-details/', AccountProductRelationshipView.as_view(), name='apd_analysis_details'),
    path('apr/summary/', AccountProductRelationshipView.as_view(), name='summary'),
    path('apr/whitespace/', AccountProductRelationshipView.as_view(), name='whitespace'),
    path('apr/analysis-summary/', AccountProductRelationshipView.as_view(), name='analysis_summary'),

    path('apr/tech-relationships/', TechRelationshipView.as_view(), name='tech_relationships'),
]
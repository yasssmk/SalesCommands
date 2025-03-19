from django.urls import path
from .views import AccountProductDetailView, TechRelationshipView



app_name = 'account_product_detail'

urlpatterns = [
    # Main CRUD endpoints
    path('', AccountProductDetailView.as_view(), name='list'),  # GET (list) and POST
    path('<int:pk>/', AccountProductDetailView.as_view(), name='detail'),  # GET, PUT, PATCH, DELETE for specific instance
    
    # Analysis endpoints
    path('<int:pk>/analyze/', AccountProductDetailView.as_view(), name='apd_analyze'),
    path('<int:pk>/refresh-analysis/', AccountProductDetailView.as_view(), name='apd_refresh_analysis'),
    path('<int:pk>/analysis-details/', AccountProductDetailView.as_view(), name='apd_analysis_details'),
    path('summary/', AccountProductDetailView.as_view(), name='summary'),
    path('whitespace/', AccountProductDetailView.as_view(), name='whitespace'),
    path('analysis-summary/', AccountProductDetailView.as_view(), name='analysis_summary'),

     path('tech-relationships/', TechRelationshipView.as_view(), name='tech_relationships'),
]
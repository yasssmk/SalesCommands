from django.urls import path
from .views import AccountProductDetailView


app_name = 'account_product_detail'

urlpatterns = [
    # Main CRUD endpoints
    path('', AccountProductDetailView.as_view(), name='list'),  # GET (list) and POST
    path('<int:pk>/', AccountProductDetailView.as_view(), name='detail'),  # GET, PUT, PATCH, DELETE for specific instance
    
    # Analysis endpoints
    path('summary/', AccountProductDetailView.as_view(), name='summary'),
    path('whitespace/', AccountProductDetailView.as_view(), name='whitespace'),
]
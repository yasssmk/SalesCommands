from django.urls import path
from .views import AccountProductDetailView


app_name = 'account_product_detail'

urlpatterns = [
    # Main CRUD endpoints
    path('<int:account_id>/details/', AccountProductDetailView.as_view(), name='list'),
    path('<int:account_id>/details/<int:pk>/', AccountProductDetailView.as_view(), name='detail'),
    
    # Analysis endpoints
    path('<int:account_id>/details/summary/', AccountProductDetailView.as_view(), name='summary'),
    path('<int:account_id>/details/whitespace/', AccountProductDetailView.as_view(), name='whitespace'),
]
from django.urls import path
from .views import RegisterProductAdminView, LoginProductAdminView, LogoutProductAdminView, RefreshTokenView

urlpatterns = [
    path('register/', RegisterProductAdminView.as_view(), name='register_product_admin'),
    path('login/', LoginProductAdminView.as_view(), name='login_product_admin'),
    path('logout/', LogoutProductAdminView.as_view(), name='logout_product_admin'),
    path('refresh/', RefreshTokenView.as_view(), name='refresh_product_admin_token'),
    # path('update-password/', UpdatePasswordView.as_view(), name='update-password')
]
from django.urls import path
from .views import AdminCreateUserView, UserLoginView, UserLogoutView, UserRefreshTokenView

urlpatterns = [
    path('admin-create/', AdminCreateUserView.as_view(), name='admin_create_user'),
    path('login/', UserLoginView.as_view(), name='login'),
    path('logout/', UserLogoutView.as_view(), name='logout'),

]
"""
URL configuration for salescommands project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include

app_key = "app/"
end_user_key = "client/"
product_admin_key = "product_admin/"

urlpatterns = [
    path('admin/', admin.site.urls),
    path(app_key+'accounts/', include('apps.accounts_app.accounts.urls')),
    path(app_key+'orgunits/', include('apps.accounts_app.org_units.urls')),
    path(app_key+'account-products/', include('apps.accounts_app.account_product_detail.urls')), 
    path(app_key+'products/', include('apps.products.urls')),
    path(end_user_key, include('end_users.urls')),
]

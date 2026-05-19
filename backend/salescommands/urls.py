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
from django.http import JsonResponse


# =========================================================================
# HEALTHCHECK ENDPOINT - For Render load balancer
# =========================================================================

def healthz(request):
    """
    Simple healthcheck endpoint for load balancer.
    
    Returns 200 OK without database query for fast response.
    Used by Render to determine if the service is alive.
    
    This endpoint:
    - Does NOT query the database (avoids unnecessary load)
    - Returns JSON for easy parsing
    - Always returns 200 (unless application is completely down)
    
    For database-aware health checks, use a dedicated monitoring endpoint.
    """
    return JsonResponse({
        'status': 'ok',
        'service': 'salescommands'
    }, status=200)


# =========================================================================
# URL PATTERNS
# =========================================================================

app_key = "app/"
end_user_key = "client/"
product_admin_key = "product_admin/"
ai_insights = "insights/"
campaign_key = "campaign/"

urlpatterns = [
    # Healthcheck (MUST be at top for performance)
    path('healthz/', healthz, name='healthz'),

    # Core infrastructure endpoints (operation polling, etc.)
    path('core/', include('core.urls')),

     # Ops test endpoints (AJOUTER CETTE LIGNE)
    path('ops/', include('ops.urls')),

    path('admin/', admin.site.urls),

    #APP MODULE
    path('company-accounts/', include('app_modules.accounts.urls')),
    path('territories/', include('app_modules.territories.urls')),
    path('contacts/', include('app_modules.contacts.urls')),
    path('decision_cycles/', include('app_modules.decision_cycles.urls')),
    path('module-activities/', include('app_modules.activities.urls')),
    path('campaigns/', include('app_modules.campaigns.urls')),
    path('module-signals/', include('app_modules.signals.urls')),
    path('module-ai-pipelines/', include('app_modules.ai_pipelines.urls')),
    path('tech-catalog/', include('app_modules.tech_catalog.urls')),

    # Path to validate 
    path(app_key+'accounts/', include('apps.accounts.urls')),
    path('leads/', include('apps.leads.urls')),
    path('activities/', include('apps.activities.urls')),
    path('opportunities/', include('apps.opportunities.urls')),
    path('signals/', include('apps.signals.urls')),
    path(campaign_key, include('apps.campaign.urls')),
    # path(app_key+'orgunits/', include('apps.accounts_app.org_units.urls')),
    # path(app_key+'account-products/', include('apps.accounts_app.account_product_detail.urls')), 
    path(app_key+'products/', include('apps.products.urls')),
    path(end_user_key, include('end_users.urls')),
    path(ai_insights, include('apps.sales_insight.urls')),
    path(product_admin_key, include("product_admin.urls")),


]

from django.shortcuts import render
from django.http import JsonResponse
from .models import Account
import json

#For testing purpose, remove later and add crsf protection
from django.views.decorators.csrf import csrf_exempt

# Create your views here.

@csrf_exempt #TO BE REMOVED
def create_account(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            account = Account.objects.create(
                name=data['name'],
                industry=data.get('industry', ''),
                address=data.get('address', ''),
                city=data.get('city', ''),
                post_code=data.get('post_code',''),
                country=data.get('country',''),
                website=data.get('website',''),
                type=data.get('type',''),
            )
            return JsonResponse({'id': account.id, 'name': account.name}, status=201)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Invalid request method'}, status=405)
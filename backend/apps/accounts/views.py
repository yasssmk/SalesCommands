from django.shortcuts import render
from django.http import JsonResponse
from rest_framework.response import Response
from rest_framework import status
from .models import Account
from rest_framework.decorators import api_view
import json

#For testing purpose, remove later and add crsf protection
from django.views.decorators.csrf import csrf_exempt

# Create your views here.

@api_view(['POST'])
def create_account(request):
    if request.method == 'POST':
        try:
            data = request.data  # DRF handles JSON parsing automatically
            account = Account.objects.create(
                name=data['name'],
                industry=data.get('industry', ''),
                address=data.get('address', ''),
                city=data.get('city', ''),
                post_code=data.get('post_code', ''),
                country=data.get('country', ''),
                website=data.get('website', ''),
                type=data.get('type', ''),
            )
            return Response({'id': account.id, 'name': account.name}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
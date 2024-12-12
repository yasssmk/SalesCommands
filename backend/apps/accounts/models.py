from django.db import models

# Create your models here.

class Account(models.Model):

    name = models.CharField(max_length=255, unique=True)
    industry = models.CharField(max_length=100, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    city = models.TextField(max_length=20, blank=True, null=True)
    post_code = models.CharField(max_length=20, blank=True, null=True)
    country = models.TextField(max_length=20, blank=True, null=True)
    website = models.CharField(max_length=255, unique=False)
    type = models.TextField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name   

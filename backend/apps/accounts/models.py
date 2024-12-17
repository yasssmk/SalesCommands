from django.db import models
from django.conf import settings
from phonenumber_field.modelfields import PhoneNumberField

# Create your models here.

class Account(models.Model):

    # Basic Information
    company_name = models.CharField(max_length=255, null=True)
    industry = models.CharField(max_length=100, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    city = models.TextField(max_length=50, blank=True, null=True)
    post_code = models.CharField(max_length=20, blank=True, null=True)
    country = models.TextField(max_length=50, blank=True, null=True)
    website = models.CharField(max_length=255, unique=False, blank=True, null=True)
    type = models.TextField(max_length=50, blank=True, null=True)
    phone_number = PhoneNumberField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # account_owner = models.ForeignKey(
    #     settings.AUTH_USER_MODEL,
    #     on_delete=models.CASCADE,
    #     related_name="accounts_owned",
    #     null=True,
    #     blank=True
    # )
    # account_logo = models.ImageField(upload_to='account_logos/', blank=True, null=True)

    # Segmentation
    number_of_employees = models.PositiveIntegerField(blank=True, null=True)
    potential = models.DecimalField(
        max_digits=15,  # To handle large monetary values
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Potential revenue based on products prices and target users."
    )
    classification = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Classification of account (e.g., SMB, Enterprise, etc.)."
    )

    # Parent-Child Relationship
    parent_company = models.ForeignKey(
        'self',  # Refers to the same model
        on_delete=models.CASCADE,
        related_name='child_companies',
        blank=True,
        null=True,
        help_text="Link to a parent company if this is a child company."
    )
    is_parent_company = models.BooleanField(default=False)
    is_child_company = models.BooleanField(default=False)
    

    class Meta:
        db_table = 'company_accounts'
        unique_together = ('company_name', 'city', 'country')

    def __str__(self):
        return self.company_name  
    


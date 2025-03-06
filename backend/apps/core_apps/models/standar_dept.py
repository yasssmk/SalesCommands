from django.db import models
from django.utils.translation import gettext_lazy as _

class StandardDepartment(models.Model):
    """
    A controlled list of standard department categories for mapping.
    """

    class DepartmentChoices(models.TextChoices):
        GENERAL_MANAGEMENT = "General Management", _("General Management")
        HR = "HR", _("Human Resources (HR)")
        FINANCE = "Finance", _("Finance & Accounting")
        IT = "IT", _("Information Technology (IT)")
        MARKETING = "Marketing", _("Marketing & Communications")
        SALES = "Sales", _("Sales & Business Development")
        CUSTOMER_SUPPORT = "Customer Support", _("Customer Support & Success")
        OPERATIONS = "Operations", _("Operations & Supply Chain")
        LEGAL = "Legal", _("Legal & Compliance")
        PROCUREMENT = "Procurement", _("Procurement & Vendor Management")
        ENGINEERING = "Engineering", _("Engineering & R&D")
        PRODUCT_MANAGEMENT = "Product Management", _("Product Management")
        DATA_ANALYTICS = "Data & Analytics", _("Data & Analytics")
        SECURITY_RISK = "Security & Risk Management", _("Security & Risk Management")
        HEALTHCARE_ADMIN = "Healthcare Administration", _("Healthcare Administration")
        CLINICAL_MEDICAL = "Clinical & Medical Staff", _("Clinical & Medical Staff")
        RETAIL_OPERATIONS = "Retail Operations", _("Retail & Store Operations")
        MANUFACTURING = "Manufacturing", _("Manufacturing & Production")
        LOGISTICS = "Logistics", _("Logistics & Transportation")
        CONSTRUCTION = "Construction", _("Construction & Engineering")
        EDUCATION_TRAINING = "Education & Training", _("Education & Training")
        GOVERNMENT = "Government", _("Government & Public Services")
        MEDIA = "Media", _("Media & Content Creation")

    name = models.CharField(
        max_length=50, 
        choices=DepartmentChoices.choices, 
        unique=True, 
        verbose_name=_("Standard Department Name")
    )

    class Meta:
        db_table = "standard_departments"
        verbose_name = _("Standard Department")
        verbose_name_plural = _("Standard Departments")
        ordering = ["name"]

    def __str__(self):
        return self.get_name_display()
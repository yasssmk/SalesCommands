from django.db import models
from apps.core_apps.models import BaseModelApp
from core.client_scope import ClientScopeManager
from django.utils.translation import gettext_lazy as _
from apps.core_apps.models import StandardDepartment


class Product(BaseModelApp, ClientScopeManager.ModelMixin):


    product_name = models.CharField(
        max_length=255, 
        verbose_name=_('Product Name'),
    )

 
    description = models.TextField(
        blank=True, 
        null=True, 
        verbose_name=_("Marketing Description")
    )

    target_categories = models.ManyToManyField(
        StandardDepartment,
        blank=True,
        related_name="products_for_category",
        verbose_name=_("Standard Department Categories")
    )

    # AI & Sales Insights
    competitors = models.JSONField(blank=True, null=True, verbose_name=_("Most Frequent Competitors"))
    key_features = models.JSONField(
        blank=True, 
        null=True, 
        default=list,
        verbose_name=_("Key Features"),
        help_text=_("List of product features with their functions and roles")
    )
    
    key_benefits = models.JSONField(
        blank=True, 
        null=True, 
        default=list,
        verbose_name=_("Key Benefits"),
        help_text=_("Tangible values the product delivers to customers")
    )

    typical_implementation_time = models.PositiveIntegerField(
        blank=True, 
        null=True, 
        verbose_name=_("Typical Implementation Time (Days)"),
        help_text=_("Average number of days to implement this product")
    )

    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=['product_name'],
        index_fields=[]
    )):
        db_table = 'products'
        verbose_name = _("Product")
        verbose_name_plural = _("Products")
        ordering = ['product_name']

    def __str__(self):
        return f"{self.product_name}"
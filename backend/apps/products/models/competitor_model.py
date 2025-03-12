from django.db import models
from apps.core_apps.models import BaseModelApp
from core.client_scope import ClientScopeManager
from django.utils.translation import gettext_lazy as _
from .product_model import Product

class Competitor(BaseModelApp, ClientScopeManager.ModelMixin):
    name = models.CharField(max_length=255, verbose_name=_('Competitor Name'))
    description = models.TextField(blank=True, null=True, verbose_name=_("Description"))
    website = models.URLField(blank=True, null=True, verbose_name=_("Website"))
    
    # Many-to-many relationship with Product
    products = models.ManyToManyField(
        Product, 
        related_name='competitor_list',
        blank=True,
        verbose_name=_("Competing Products")
    )
    
    # Battle cards for competitive differentiation
    battle_cards = models.JSONField(
        blank=True, 
        null=True, 
        default=dict,
        verbose_name=_("Battle Cards"),
        help_text=_("Competitive differentiation points")
    )
    
    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=['name'],
        index_fields=[]
    )):
        db_table = 'competitors'
        verbose_name = _("Competitor")
        verbose_name_plural = _("Competitors")
        ordering = ['name']

    def __str__(self):
        return self.name
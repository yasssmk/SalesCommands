# # apps/sequence/models/sequence_template.py
# from django.db import models
# from django.utils.translation import gettext_lazy as _
# from core.client_scope import ClientScopeManager
# from apps.core_apps.models import BaseModelApp
# import json

# class SequenceTemplate(BaseModelApp, ClientScopeManager.ModelMixin):
#     """
#     Represents a sequence template type for campaigns
#     """
#     class SequenceType(models.TextChoices):
#         CHASING = 'CHASING', _('Standard Chasing')

    
#     name = models.CharField(
#         max_length=100,
#         verbose_name=_('Template Name')
#     )
    
#     description = models.TextField(
#         blank=True,
#         null=True,
#         verbose_name=_('Description')
#     )
    
#     sequence_type = models.CharField(
#         max_length=30,
#         choices=SequenceType.choices,
#         unique=True,
#         verbose_name=_('Sequence Type')
#     )
    
#     class Meta:
#         verbose_name = _('Sequence Template')
#         verbose_name_plural = _('Sequence Templates')
#         indexes = [
#             models.Index(fields=['sequence_type']),
#         ]

#     def __str__(self):
#         return f"{self.name} ({self.get_sequence_type_display()})"
    
#     def get_configuration(self, channel_config='standard'):
#         """
#         Get sequence configuration based on channel configuration
        
#         Args:
#             channel_config: One of 'standard', 'without_phone', 'without_email', 'phone_only'
            
#         Returns:
#             Dictionary with sequence steps
#         """
#         from apps.sequence.sequences.chasing_sequence import ChasingSequence
        
#         # Map sequence types to their configuration methods
#         config_methods = {
#             self.SequenceType.CHASING: {
#                 'standard': ChasingSequence.get_standard_sequence,
#                 'without_phone': ChasingSequence.get_sequence_without_phone,
#                 'without_email': ChasingSequence.get_sequence_without_email,
#                 'phone_only': ChasingSequence.get_sequence_phone_only
#             },

#             # Future implementations for RENEWAL and FOLLOW_UP would go here
#             # For now, they'll fall back to STANDARD
#         }
        
#         # Get the configuration method for this sequence type and channel config
#         if self.sequence_type in config_methods and channel_config in config_methods[self.sequence_type]:
#             return config_methods[self.sequence_type][channel_config]()
        
#         # Fall back to standard chasing sequence if not found
#         return ChasingSequence.get_standard_sequence()
    
#     @classmethod
#     def get_all_templates(cls):
#         """Get all available sequence templates"""
#         templates = cls.objects.all()
        
#         # If no templates exist, create them
#         if not templates.exists():
#             cls.create_default_templates()
#             templates = cls.objects.all()
            
#         return templates
    
#     @classmethod
#     def create_default_templates(cls):
#         """Create the default sequence templates"""
#         # Standard Chasing Sequence
#         cls.objects.create(
#             name="Standard Chasing Sequence",
#             description="Standard sequence with phone, email, and LinkedIn touchpoints",
#             sequence_type=cls.SequenceType.STANDARD
#         )
        
#         # Accelerated Chasing Sequence
#         cls.objects.create(
#             name="Accelerated Chasing Sequence",
#             description="Accelerated sequence with shorter delays between steps",
#             sequence_type=cls.SequenceType.ACCELERATED
#         )
        
#         # Gentle Follow-up Sequence
#         cls.objects.create(
#             name="Gentle Follow-up Sequence",
#             description="Gentle sequence with longer delays and fewer touchpoints",
#             sequence_type=cls.SequenceType.GENTLE
#         )
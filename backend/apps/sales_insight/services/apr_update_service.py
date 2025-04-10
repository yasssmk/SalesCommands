# # apps/sales_insight/services/apr_update_service.py

# from django.utils import timezone
# from django.db import transaction
# from apps.accounts.models import Account, AccountProductRelationship
# from apps.products.models import Product
# from core.error_messages import CoreErrorMessages
# from core.exceptions import StandardizedValidationError
# import json
# import re

# class APRUpdateService:
#     """
#     Service for updating Account Product Detail models with insights
#     from signal analysis.
#     """
    
#     @classmethod
#     def apply_analysis_to_apr(cls, analysis_results, account_id, product_id, user=None):
#         """
#         Apply analysis results to an existing or new AccountProductDetail.
        
#         Args:
#             analysis_results: Results from aprAnalysisService
#             account_id: Account ID
#             product_id: Product ID
#             user: User performing the update
            
#         Returns:
#             tuple: (AccountProductDetail instance, boolean indicating if created)
            
#         Raises:
#             StandardizedValidationError: If there's an issue with inputs or processing
#         """
#         if not analysis_results.get("analysis_results") or "error" in analysis_results.get("analysis_results", {}):
#             raise StandardizedValidationError(
#                 CoreErrorMessages.INVALID_DATA.format(
#                     detail="Analysis results are incomplete or contain errors"
#                 )
#             )
        
#         if not analysis_results.get("apr_structured_data"):
#             raise StandardizedValidationError(
#                 CoreErrorMessages.INVALID_DATA.format(
#                     detail="Missing structured data for apr update"
#                 )
#             )
            
#         try:
#             account = Account.objects.get(id=account_id)
#             product = Product.objects.get(id=product_id)
#         except (Account.DoesNotExist, Product.DoesNotExist):
#             raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
        
#         # Try to find existing apr
#         try:
#             apr = AccountProductRelationship.objects.get(
#                 account_id=account_id,
#                 product_id=product_id
#             )
#             created = False
#         except AccountProductRelationship.DoesNotExist:
#             # Create new apr with minimal info
#             apr = AccountProductRelationship(
#                 account=account,
#                 product=product,
#                 estimated_units=1,  # Default minimum
#                 client_id=account.client_id
#             )
#             created = True
        
#         with transaction.atomic():
#             # Get structured data ready for the apr
#             structured_data = analysis_results["apr_structured_data"]
            
#             # Update apr with structured analysis data
#             apr.objectives_alignment = structured_data.get("objectives_alignment")
#             apr.pain_points_coverage = structured_data.get("pain_points_coverage")
#             apr.economic_impact = structured_data.get("economic_impact")
#             apr.coverage_stats = analysis_results.get("coverage_stats") or structured_data.get("coverage_stats")
#             apr.ai_relevance_score = structured_data.get("ai_relevance_score")
            
#             # Set last analysis date
#             apr.last_analysis_date = timezone.now()
            
            
#             # Format analysis for notes if requested
#             notes_update = cls._format_analysis_for_notes(analysis_results)
            
#             # Update notes - append rather than replace
#             if notes_update:
#                 existing_notes = apr.notes or ""
#                 timestamp = timezone.now().strftime("%Y-%m-%d %H:%M")
                
#                 new_notes = f"{existing_notes}\n\n=== AI Analysis {timestamp} ===\n{notes_update}"
#                 apr.notes = new_notes
            
#             # Try to extract estimated units from economic impact if available
#             if structured_data.get("economic_impact") and "units_count" in structured_data["economic_impact"]:
#                 units_count = structured_data["economic_impact"]["units_count"]
#                 if isinstance(units_count, int) and units_count > 0:
#                     apr.estimated_units = units_count
            
#             # Add metadata about this update
#             if not apr.historical_data:
#                 apr.historical_data = {}
                
#             if "ai_analysis" not in apr.historical_data:
#                 apr.historical_data["ai_analysis"] = []
                
#             # Record analysis metadata for audit
#             analysis_meta = {
#                 "timestamp": timezone.now().isoformat(),
#                 "coverage_stats": analysis_results.get("coverage_stats", {}),
#                 "updated_by": str(user.id) if user else None,
#                 "entity_type": analysis_results.get("entity_type"),
#                 "entity_id": analysis_results.get("entity_id")
#             }
            
#             apr.historical_data["ai_analysis"].append(analysis_meta)
            
#             # Save the apr with the user context
#             apr.save(user=user)
            
#             return apr, created
    
#     @classmethod
#     def _format_analysis_for_notes(cls, analysis_results):
#         """Format analysis results into a readable notes format"""
#         if not analysis_results or "analysis_results" not in analysis_results:
#             return ""
            
#         results = analysis_results["analysis_results"]
#         notes = []
        
#         # Add a summary section
#         notes.append("SUMMARY:")
#         coverage_stats = analysis_results.get("coverage_stats", {})
#         if coverage_stats:
#             notes.append(f"• Overall Product Fit: {coverage_stats.get('overall_coverage_percent', 0)}%")
#             notes.append(f"• Objectives Coverage: {coverage_stats.get('objectives_coverage_percent', 0)}%")
#             notes.append(f"• Pain Points Coverage: {coverage_stats.get('pain_points_coverage_percent', 0)}%")
        
#         notes.append("")
        
#         # Format objective alignment
#         if "objectives" in results:
#             notes.append("OBJECTIVES ALIGNMENT:")
#             for obj in results["objectives"]:
#                 objective = obj.get("objectiveStatement", "")
#                 matches = obj.get("matchingProductBenefit", [])
#                 why = obj.get("whyItHelps", [])
                
#                 # Add signal quality if available
#                 quality_info = ""
#                 if "signal_quality" in obj:
#                     quality = obj["signal_quality"]
#                     confirmation_count = quality.get("confirmation_count", 1)
#                     if confirmation_count > 1:
#                         quality_info = f" (confirmed {confirmation_count} times)"
                
#                 if objective:
#                     notes.append(f"• {objective}{quality_info}")
                    
#                     if matches:
#                         notes.append(f"  - Matching benefits: {', '.join(matches)}")
                    
#                     if why:
#                         formatted_why = '; '.join(why) if isinstance(why, list) else why
#                         notes.append(f"  - Why it helps: {formatted_why}")
            
#             notes.append("")
        
#         # Format pain points coverage
#         if "painPointsAnalysis" in results and "painsCoverage" in results["painPointsAnalysis"]:
#             notes.append("PAIN POINTS COVERAGE:")
#             for pain in results["painPointsAnalysis"]["painsCoverage"]:
#                 pain_point = pain.get("painPoint", "")
#                 features = pain.get("matchingProductFeatures", [])
#                 benefits = pain.get("matchingProductBenefits", [])
#                 why = pain.get("whyItHelps", [])
                
#                 # Add signal quality if available
#                 quality_info = ""
#                 if "signal_quality" in pain:
#                     quality = pain["signal_quality"]
#                     confirmation_count = quality.get("confirmation_count", 1)
#                     if confirmation_count > 1:
#                         quality_info = f" (confirmed {confirmation_count} times)"
                
#                 if pain_point:
#                     notes.append(f"• {pain_point}{quality_info}")
                    
#                     if features:
#                         notes.append(f"  - Matching features: {', '.join(features)}")
                    
#                     if benefits:
#                         notes.append(f"  - Matching benefits: {', '.join(benefits)}")
                    
#                     if why:
#                         formatted_why = '; '.join(why) if isinstance(why, list) else why
#                         notes.append(f"  - Why it helps: {formatted_why}")
            
#             notes.append("")
        
#         # Format economic impact
#         if "economicImpact" in results:
#             notes.append("ECONOMIC IMPACT:")
#             economic = results["economicImpact"]
            
#             if economic.get("currentPainCost"):
#                 notes.append(f"• Current pain cost: {economic['currentPainCost']}")
            
#             if economic.get("timeOrMoneySaved"):
#                 notes.append(f"• Potential savings: {economic['timeOrMoneySaved']}")
            
#             if economic.get("unitsThatMatter"):
#                 notes.append(f"• Key units: {economic['unitsThatMatter']}")
            
#             if economic.get("existingSolutionCost"):
#                 notes.append(f"• Existing solution cost: {economic['existingSolutionCost']}")
            
#             if economic.get("estimatedAccountPotential"):
#                 notes.append(f"• Estimated potential: {economic['estimatedAccountPotential']}")
            
#             additional_costs = economic.get("additionalCosts", [])
#             if additional_costs:
#                 formatted_costs = ', '.join(additional_costs) if isinstance(additional_costs, list) else additional_costs
#                 notes.append(f"• Additional costs: {formatted_costs}")
        
#         return "\n".join(notes)
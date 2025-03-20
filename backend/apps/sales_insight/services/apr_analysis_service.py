# apps/sales_insight/services/apd_analysis_service.py

from django.utils import timezone
from django.db.models import Q
from apps.accounts.models import Account
from apps.products.models import Product
from apps.LLM_calls.services import LLMProviderService
from ..models import Signal
from ..services.apd_prompts_service import call_second_llm_for_alignment
from ..services.signal_lifecycle_service import SignalLifecycleService
from core.exceptions import CoreErrorMessages, StandardizedValidationError
import json
import re

class APRAnalysisService:
    """
    Service for analyzing account/org unit signals in relation to products,
    with awareness of signal lifecycle and quality.
    """
    
    @classmethod
    def analyze_product_alignment(cls, account_id, product_id, org_unit_id=None, contact_id=None):
        """
        Analyze alignment between account/org unit signals and product features/benefits.
        
        Args:
            account_id: ID of the account to analyze
            product_id: ID of the product to compare against
            org_unit_id: Optional ID of a specific org unit to analyze
            contact_id: Optional ID of a specific contact to include in analysis
            
        Returns:
            dict: Comprehensive analysis results with signal quality metadata and
                 structured data suitable for APD storage
                 
        Raises:
            StandardizedValidationError: If entities don't exist or belong to different clients
        """
        try:
            
            # Fetch required entities
            account = Account.objects.get(id=account_id)
            product = Product.objects.get(id=product_id)
                   
        except Account.DoesNotExist:
            raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
        except Product.DoesNotExist:
            raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)

        
        # Prepare the base result structure
        result = {
            'account_id': str(account_id),
            'entity_type': 'account',
            'entity_id': account_id,
            'product_id': str(product_id),
            'entity_name': account.company_name,
            'product_name': product.product_name,
            'signal_quality': {
                'objectives': {},
                'pain_points': {}
            },
            'analysis_results': {},  # Raw LLM analysis
            'apd_structured_data': {  # Pre-formatted for APD storage
                'objectives_alignment': None,
                'pain_points_coverage': None,
                'economic_impact': None,
                'coverage_stats': None,
                'ai_relevance_score': None
            }
        }
        
        # Get signals with lifecycle info
        signals_data = cls._get_quality_signals(account_id, org_unit_id)
        
        # Extract qualification data
        objectives = cls._extract_qualification_with_quality(
            signals_data, 
            'objectives',
            result['signal_quality']['objectives']
        )
        
        pain_points = cls._extract_qualification_with_quality(
            signals_data, 
            'pain_points',
            result['signal_quality']['pain_points']
        )
        
        # Get product features/benefits
        product_benefits = product.key_benefits or []
        product_features = product.key_features or []
        combined_product_info = product_benefits + product_features
        replaceable_tech_stack = cls._extract_replaceable_tech_stack(account, product_id)
        
        # Check if we have enough data for analysis
        if not objectives and not pain_points:
            result['message'] = "Insufficient data for analysis - no objectives or pain points found"
            return result
        
        if not combined_product_info:
            result['message'] = "Insufficient data for analysis - no product benefits or features defined"
            return result
        
        # Call LLM service for alignment analysis
        try:
            llm_service = LLMProviderService()
            # Ensure we pass all required parameters
            alignment_json = call_second_llm_for_alignment(
                account_objectives=objectives,
                account_pain_points=pain_points,
                product_benefits=combined_product_info,
                replaceable_tech_stack=replaceable_tech_stack  # Make sure this parameter is passed
            )
        except Exception as e:
            print(f"Error calling LLM: {str(e)}")
            import traceback
            traceback.print_exc()
            raise StandardizedValidationError(
                CoreErrorMessages.SERVICE_ERROR
            )
        
        # Parse and enhance the response with signal quality
        analysis_results = cls._parse_llm_response(alignment_json)
        
        if analysis_results:
            # Check for error in analysis results
            if "error" in analysis_results:
                raise StandardizedValidationError(
                    CoreErrorMessages.PROCESSING_FAILED.format(
                        message=analysis_results["error"]
                    )
                )
                
            # Add signal quality context to results
            cls._enhance_results_with_signal_quality(
                analysis_results, 
                result['signal_quality']
            )
            
            # Calculate coverage statistics
            coverage_stats = cls._calculate_coverage_stats(
                analysis_results, 
                objectives, 
                pain_points
            )
            
            result['coverage_stats'] = coverage_stats

            # Prepare structured data for APD storage
            cls._prepare_apd_structured_data(
                result['apd_structured_data'],
                analysis_results,
                coverage_stats,
                replaceable_tech_stack
            )

        result['analysis_results'] = analysis_results

        return result
    
    @classmethod
    def _get_quality_signals(cls, account_id):
        """
        Get signals with quality indicators (confirmation count, recency, etc.)
        for objectives, pain points, and implications.
        
        Returns dict with structure:
        {
            "objectives": {
                "signals": [Signal objects],
                "quality_metadata": {
                    "signal_id": {
                        "confirmation_count": n,
                        "last_confirmed": date,
                        "effective_status": status,
                        "age_days": days
                    }
                }
            },
            "pain_points": {...},
            "implications": {...}
        }
        """
        result = {
            "objectives": {"signals": [], "quality_metadata": {}},
            "pain_points": {"signals": [], "quality_metadata": {}},
            "implications": {"signals": [], "quality_metadata": {}} 
        }
        
        # Base query for account signals
        base_query = Signal.objects.filter(
            account_id=account_id,
            status__in=[Signal.Status.APPROVED, Signal.Status.APPLIED]
        )
        
        
        # Process each field type
        for field_name in ["objectives", "pain_points", "implications"]:
            field_signals = base_query.filter(field_name=field_name)
            
            for signal in field_signals:
                result[field_name]["signals"].append(signal)
                
                # Get effective status that considers expiration
                effective_status = SignalLifecycleService.get_effective_status(signal)
                
                # Calculate age in days
                age_days = (timezone.now() - signal.last_confirmed_at).days
                
                # Store quality metadata
                result[field_name]["quality_metadata"][str(signal.id)] = {
                    "confirmation_count": signal.confirmation_count,
                    "last_confirmed": signal.last_confirmed_at,
                    "effective_status": effective_status,
                    "age_days": age_days,
                    "source": signal.source
                }
        
        return result
    
    @classmethod
    def _extract_qualification_with_quality(cls, signals_data, field_name, quality_output):
        """
        Extract qualification data from signals with quality indicators.
        Updates quality_output with metadata for use in UI highlighting.
        
        Returns:
            list: Qualification items (objectives or pain points)
        """
        if field_name not in signals_data:
            return []
            
        items = []
        signal_field_map = {}  # Maps item text to its source signal
        
        # Extract items from signals
        for signal in signals_data[field_name]["signals"]:
            if isinstance(signal.value, list):
                for item in signal.value:
                    item_text = item
                    if isinstance(item, dict) and "statement" in item:
                        item_text = item["statement"]
                    elif isinstance(item, dict) and "description" in item:
                        item_text = item["description"]
                    
                    if item_text not in items:
                        items.append(item_text)
                        signal_field_map[item_text] = str(signal.id)
            elif isinstance(signal.value, str):
                if signal.value not in items:
                    items.append(signal.value)
                    signal_field_map[signal.value] = str(signal.id)
        
        # Build quality output for UI highlighting
        for item in items:
            if item in signal_field_map:
                signal_id = signal_field_map[item]
                if signal_id in signals_data[field_name]["quality_metadata"]:
                    metadata = signals_data[field_name]["quality_metadata"][signal_id]
                    quality_output[item] = {
                        "confirmation_count": metadata["confirmation_count"],
                        "last_confirmed": metadata["last_confirmed"].isoformat() if metadata["last_confirmed"] else None,
                        "effective_status": metadata["effective_status"],
                        "age_days": metadata["age_days"],
                        "source": metadata["source"],
                        "signal_id": signal_id
                    }
        
        return items
    
    @classmethod
    def _parse_llm_response(cls, llm_response):
        """Parse LLM response into structured analysis results"""
        try:
            if isinstance(llm_response, str):
                # Try to extract JSON if it's wrapped in markdown or other text
                import re
                json_match = re.search(r'```json\s*(.*?)\s*```', llm_response, re.DOTALL)
                if json_match:
                    try:
                        return json.loads(json_match.group(1))
                    except json.JSONDecodeError:
                        # If that didn't work, try loading the whole string
                        try:
                            return json.loads(llm_response)
                        except json.JSONDecodeError:
                            return {"error": CoreErrorMessages.PROCESSING_FAILED.format(
                                message="Failed to parse LLM response"
                            )}
                else:
                    # If no JSON code block, try loading the whole string
                    try:
                        return json.loads(llm_response)
                    except json.JSONDecodeError:
                        return {"error": CoreErrorMessages.PROCESSING_FAILED.format(
                            message="Failed to parse LLM response"
                        )}
            else:
                return llm_response
        except Exception as e:
            return {"error": CoreErrorMessages.PROCESSING_FAILED.format(
                message=f"Failed to process LLM response: {str(e)}"
            )}
        
    @classmethod
    def _enhance_results_with_signal_quality(cls, analysis_results, signal_quality):
        """
        Enhance analysis results with signal quality information.
        This adds quality indicators to each objective and pain point in the results.
        """
        if not analysis_results or "error" in analysis_results:
            return
        
        # Enhance objectives
        if "objectives" in analysis_results and signal_quality.get("objectives"):
            for obj in analysis_results["objectives"]:
                objective_text = obj.get("objectiveStatement", "")
                if objective_text in signal_quality["objectives"]:
                    obj["signal_quality"] = signal_quality["objectives"][objective_text]
        
        # Enhance pain points
        if "painPointsAnalysis" in analysis_results and "painsCoverage" in analysis_results["painPointsAnalysis"]:
            for pain in analysis_results["painPointsAnalysis"]["painsCoverage"]:
                pain_text = pain.get("painPoint", "")
                if pain_text in signal_quality.get("pain_points", {}):
                    pain["signal_quality"] = signal_quality["pain_points"][pain_text]
    
    @classmethod
    def _calculate_coverage_stats(cls, analysis_results, objectives, pain_points):
        """
        Calculate coverage statistics based on analysis results.
        Returns metrics about how well product covers objectives and pain points.
        """
        stats = {
            "objectives_coverage_percent": 0,
            "pain_points_coverage_percent": 0,
            "overall_coverage_percent": 0,
        }
        
        if not analysis_results or "error" in analysis_results:
            return stats
        
        # Calculate objective coverage
        objectives_count = len(objectives)
        covered_objectives = 0
        objective_quality_sum = 0
        
        if objectives_count > 0 and "objectives" in analysis_results:
            for obj in analysis_results["objectives"]:
                has_match = obj.get("matchingProductBenefit") and len(obj.get("matchingProductBenefit", [])) > 0
                
                if has_match:
                    covered_objectives += 1
                    
                    # Add quality weighting if available
                    if "signal_quality" in obj:
                        confirmation_count = obj["signal_quality"].get("confirmation_count", 1)
                        confidence = obj["signal_quality"].get("confidence", 50) / 100
                        
                        # Higher confirmation count and confidence increases quality
                        quality_score = min(1.0, (confirmation_count * 0.2) + confidence)
                        objective_quality_sum += quality_score
            
            stats["objectives_coverage_percent"] = round((covered_objectives / objectives_count) * 100)
        
        # Calculate pain points coverage
        pain_points_count = len(pain_points)
        covered_pain_points = 0
        pain_quality_sum = 0
        
        if pain_points_count > 0 and "painPointsAnalysis" in analysis_results:
            pains_coverage = analysis_results["painPointsAnalysis"].get("painsCoverage", [])
            for pain in pains_coverage:
                has_match = (
                    (pain.get("matchingProductFeatures") and len(pain.get("matchingProductFeatures", [])) > 0) or
                    (pain.get("matchingProductBenefits") and len(pain.get("matchingProductBenefits", [])) > 0)
                )
                
                if has_match:
                    covered_pain_points += 1
                    
                    # Add quality weighting if available
                    if "signal_quality" in pain:
                        confirmation_count = pain["signal_quality"].get("confirmation_count", 1)
                        confidence = pain["signal_quality"].get("confidence", 50) / 100
                        
                        # Higher confirmation count and confidence increases quality
                        quality_score = min(1.0, (confirmation_count * 0.2) + confidence)
                        pain_quality_sum += quality_score
            
            stats["pain_points_coverage_percent"] = round((covered_pain_points / pain_points_count) * 100)
        
        # Calculate overall coverage
        total_items = objectives_count + pain_points_count
        if total_items > 0:
            covered_items = covered_objectives + covered_pain_points
            stats["overall_coverage_percent"] = round((covered_items / total_items) * 100)
            
        
        return stats
    
    @classmethod
    def _prepare_apd_structured_data(cls, apd_data, analysis_results, coverage_stats, replaceable_tech_stack=None):
        """
        Prepare structured data for storage in APD model.
        This formats the LLM analysis into a structure compatible with our model fields.
        
        Args:
            apd_data: Dict to be filled with structured data
            analysis_results: Raw analysis results from LLM
            coverage_stats: Coverage statistics
        """
        if not analysis_results or "error" in analysis_results:
            return
        
        # Set coverage stats
        apd_data['coverage_stats'] = coverage_stats
        
        # Set AI relevance score based on confidence-weighted coverage
        # apd_data['ai_relevance_score'] = coverage_stats.get('confidence_weighted_coverage', 0) / 100
        apd_data['ai_relevance_score'] = 0
        # Format objectives alignment
        if "objectives" in analysis_results:
            apd_data['objectives_alignment'] = {
                "objectives": [
                    {
                        "statement": obj.get("objectiveStatement", ""),
                        "matching_benefits": obj.get("matchingProductBenefit", []),
                        "rationale": obj.get("whyItHelps", []),
                        "expected_outcome": obj.get("expectedOutcome", []),
                        "signal_quality": obj.get("signal_quality", {})
                    }
                    for obj in analysis_results["objectives"]
                ]
            }
        
        # Format pain points coverage
        if "painPointsAnalysis" in analysis_results and "painsCoverage" in analysis_results["painPointsAnalysis"]:
            apd_data['pain_points_coverage'] = {
                "pains": [
                    {
                        "pain_point": pain.get("painPoint", ""),
                        "matching_features": pain.get("matchingProductFeatures", []),
                        "matching_benefits": pain.get("matchingProductBenefits", []),
                        "rationale": pain.get("whyItHelps", []),
                        "signal_quality": pain.get("signal_quality", {})
                    }
                    for pain in analysis_results["painPointsAnalysis"]["painsCoverage"]
                ]
            }
        
        # Format economic impact
        if "valueSection" in analysis_results:
            value_section = analysis_results["valueSection"]
            
            economic_impact = {
                "cost_implications": value_section.get("costOfImplications", ""),
                "status_quo_cost": value_section.get("statusQuoCost", ""),
                "benefit_impacts": []
            }
            
            # Process product benefit impacts
            if "productBenefitImpact" in value_section:
                for benefit in value_section["productBenefitImpact"]:
                    benefit_impact = {
                        "benefit_name": benefit.get("benefitName", ""),
                        "qualitative_benefit": benefit.get("qualitativeBenefit", ""),
                        "estimated_savings": benefit.get("estimatedTimeOrMoneySaved", "")
                    }
                    economic_impact["benefit_impacts"].append(benefit_impact)
            
            # Process TCO summary
            if "tcoSummary" in value_section:
                tco_summary = value_section["tcoSummary"]
                
                economic_impact["tco_arguments"] = []
                if "arguments" in tco_summary:
                    for arg in tco_summary["arguments"]:
                        tco_arg = {
                            "title": arg.get("argumentTitle", ""),
                            "description": arg.get("argumentDescription", ""),
                            "formula": arg.get("formulaOrEstimation", ""),
                            "assumptions": arg.get("assumptions", [])
                        }
                        economic_impact["tco_arguments"].append(tco_arg)
                
                economic_impact["overall_value_statement"] = tco_summary.get("overallValueStatement", "")
            
            # Add replaceable tech stack information if provided
            if replaceable_tech_stack:
                economic_impact["replaceable_tech"] = replaceable_tech_stack
            
            apd_data['economic_impact'] = economic_impact
    
    @classmethod
    def _extract_numeric_values(cls, economic_data):
        """Extract numeric values from economic data text for easier calculation"""
        for field in ['current_pain_cost', 'potential_savings', 'existing_solution_cost', 'estimated_potential']:
            if field in economic_data and economic_data[field]:
                text = economic_data[field]
                # Look for currency amounts with regex
                currency_matches = re.findall(r'[$€£¥]?\s*[\d,]+(?:\.\d+)?(?:\s*[kKmMbBtT])?', text)
                if currency_matches:
                    # Add structured value if found
                    economic_data[f"{field}_value"] = cls._normalize_currency_value(currency_matches[0])
        
        # Extract numeric value from units if present
        if 'relevant_units' in economic_data and economic_data['relevant_units']:
            numbers = re.findall(r'\b\d+\b', economic_data['relevant_units'])
            if numbers:
                economic_data['units_count'] = int(numbers[0])
    
    @classmethod
    def _normalize_currency_value(cls, currency_str):
        """Convert currency string like $10k or €2.5M to a numeric value"""
        # Remove currency symbols and commas
        clean_str = re.sub(r'[$€£¥,\s]', '', currency_str.strip())
        
        # Handle suffixes
        multiplier = 1
        if clean_str.lower().endswith('k'):
            multiplier = 1000
            clean_str = clean_str[:-1]
        elif clean_str.lower().endswith('m'):
            multiplier = 1000000
            clean_str = clean_str[:-1]
        elif clean_str.lower().endswith('b'):
            multiplier = 1000000000
            clean_str = clean_str[:-1]
        
        try:
            return float(clean_str) * multiplier
        except ValueError:
            return None
        
    @classmethod
    def _extract_replaceable_tech_stack(cls, account, product_id=None):
        """
        Extract tech stack items that could potentially be replaced by the specified product.
        
        Args:
            account: The account object
            org_unit: Optional organization unit
            product_id: ID of the product to check replacement potential
            
        Returns:
            list: Tech stack items with replacement potential and cost information
        """
        replaceable_tech = []
        
        # Determine which entity to use for tech stack
        entity = account
        
        # Check if entity has tech stack
        if not hasattr(entity, 'current_tech_stack') or not entity.current_tech_stack:
            return replaceable_tech
        
        # Ensure tech stack is a list
        tech_stack = entity.current_tech_stack
        if not isinstance(tech_stack, list):
            tech_stack = [tech_stack]
        
        # Extract tech items that have relationship or cost data
        for index, tech_item in enumerate(tech_stack):
            # Check if this item has a relationship with the product
            has_relationship = False
            is_replaceable = False
            
            if 'relationship' in tech_item:
                relationship = tech_item['relationship']
                if str(relationship.get('product_id')) == str(product_id):
                    has_relationship = True
                    # Check if relationship type is REPLACE
                    if relationship.get('relationship_type') == 'REPLACE':
                        is_replaceable = True
            
            # Extract cost information if available
            costs = tech_item.get('costs', [])
            renewal_date = tech_item.get('renewalDate')
            approx_cost = None
            
            # Try to extract numeric cost from the costs field
            if costs:
                import re
                for cost_item in costs:
                    if isinstance(cost_item, str):
                        # Look for currency amounts
                        matches = re.findall(r'[$€£¥]?\s*[\d,]+(?:\.\d+)?(?:\s*[kKmMbBtT])?', cost_item)
                        if matches:
                            approx_cost = matches[0]
                            break
            
            # Add to replaceable if:
            # 1. It has an explicit REPLACE relationship with this product, or
            # 2. It has cost information (making it a candidate for replacement analysis)
            if is_replaceable or approx_cost:
                replaceable_tech.append({
                    'techName': tech_item.get('techName', f"Technology {index+1}"),
                    'approxCost': approx_cost or "unknown",
                    'renewalDate': renewal_date or "N/A",
                    'businessGoal': tech_item.get('businessGoal', ''),
                    'pros': tech_item.get('pros', ''),
                    'improvementPoints': tech_item.get('improvementPoints', ''),
                    'explicit_replacement': is_replaceable
                })
        
        return replaceable_tech
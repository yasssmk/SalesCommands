# apps/analysis/views/transcript_analysis_view.py

from rest_framework import status
from django.conf import settings
from rest_framework.response import Response
from openai import OpenAIError, AuthenticationError, APIError
from rest_framework.exceptions import ParseError
import openai
from core.exceptions import StandardizedValidationError, StandardizedAuthenticationFailed
from core.error_messages import CoreErrorMessages
from ..services.new_prompt import get_full_insights
from ..serializers.transript_serializer import TranscriptAnalysisSerializer
from apps.signals.services.signal_parsing_service import SignalParsingService
from apps.signals.serializers.signal_serializer_factory import SignalSerializerFactory
from core.apps_shared_methods import BaseAPIView


class TranscriptAnalysisView(BaseAPIView):
    """
    API view for analyzing transcripts using OpenAI.
    Creates signals from AI insights and returns them for user validation.
    """
    serializer_class = TranscriptAnalysisSerializer
    entity_name = 'transcript'

    def post(self, request, *args, **kwargs):
        """
        Analyze transcript using OpenAI and create signals.
        Returns created signals for user validation instead of raw insights.
        """
        try:
            # Validate incoming data
            serializer = self.serializer_class(
                data=request.data,
                context={'request': request, 'client_id': self.get_client_id()}
            )
            
            if not serializer.is_valid():
                raise StandardizedValidationError(serializer.errors)

            # Get validated data
            transcript = serializer.validated_data['transcript']
            account = serializer.validated_data['account']
            contact = serializer.validated_data.get('contact')
            
            # Process through OpenAI to get structured insights
            insights = get_full_insights(transcript)
            if not insights:
                raise StandardizedValidationError(CoreErrorMessages.PROCESSING_FAILED)
                
            # Parse insights into signals using our refactored service
            client_id = self.get_client_id()
            created_signals = SignalParsingService.parse_insights(
                insights=insights,
                account=account,
                source='transcript_analysis',
                user=request.user,
                client_id=client_id,  # Pass client_id to the service
            )
            
            # Format the response with signals by category
            response_data = {
                'success': True,
                'total_signals_count': sum(len(signals) for signals in created_signals.values() if isinstance(signals, list)),
                'signals_by_category': {}
            }
            
            # Process each signal type
            for category, signals in created_signals.items():
                if category != 'tech_stack':
                    # Handle qualification and profile signals as before
                    if signals:
                        # Serialize signals using the appropriate serializer for each type
                        serialized_signals = []
                        for signal in signals:
                            serializer = SignalSerializerFactory.get_serializer_for_instance(signal)
                            serialized_signals.append(
                                serializer(signal, context={'request': request, 'client_id': client_id}).data
                            )
                        
                        # Add to response
                        response_data['signals_by_category'][category] = {
                            'count': len(signals),
                            'signals': serialized_signals
                        }
                else:
                    # Special handling for tech_stack signals - organize by tech name
                    # Check if signals is a dictionary (grouped by tech name) or a list
                    if signals:
                        tech_stack_signals = {}
                        total_count = 0
                        
                        # First, serialize all signals
                        serialized_signals = []
                        for signal in signals:
                            serializer = SignalSerializerFactory.get_serializer_for_instance(signal)
                            serialized_signals.append(
                                serializer(signal, context={'request': request, 'client_id': client_id}).data
                            )
                        
                        # Group signals by pending_tech_name or tech_stack_summary.name
                        for serialized_signal in serialized_signals:
                            # Get tech name from pending_tech_name or tech_stack_summary
                            tech_name = None
                            
                            # First try to get from pending_tech_name (for LLM-generated signals)
                            if 'pending_tech_name' in serialized_signal and serialized_signal['pending_tech_name']:
                                tech_name = serialized_signal['pending_tech_name']
                            # Then try from tech_stack_summary (for signals with existing tech_stack)
                            elif serialized_signal.get('tech_stack_summary') and serialized_signal['tech_stack_summary'].get('name'):
                                tech_name = serialized_signal['tech_stack_summary']['name']
                            # Fallback
                            else:
                                tech_name = "Unknown Technology"
                            
                            # Initialize tech stack entry if not exists
                            if tech_name not in tech_stack_signals:
                                tech_stack_signals[tech_name] = {
                                    'tech_name': tech_name,
                                    'tech_stack': serialized_signal.get('tech_stack'),
                                    'signals': []
                                }
                            
                            # Add signal to the tech stack group
                            tech_stack_signals[tech_name]['signals'].append(serialized_signal)
                            total_count += 1
                        
                        # Convert dictionary to list of tech stacks
                        tech_stacks_list = list(tech_stack_signals.values())
                        
                        # Add to response
                        response_data['signals_by_category']['tech_stack'] = {
                            'count': total_count,
                            'tech_stacks_signals': tech_stacks_list
                        }
            
            # Include raw insights for debugging during development
            if settings.DEBUG:
                response_data['raw_insights'] = insights
            
            return Response(response_data, status=status.HTTP_200_OK)

        except APIError as e:
            raise StandardizedAuthenticationFailed(f"{CoreErrorMessages.SERVICE_AUTH_FAILED}: {str(e)}")
        except OpenAIError as e:
            raise StandardizedValidationError(f"{CoreErrorMessages.SERVICE_ERROR}: {str(e)}")
        except Exception as e:
            return self.handle_exception(e)
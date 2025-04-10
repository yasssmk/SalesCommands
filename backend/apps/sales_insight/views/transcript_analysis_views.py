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
from apps.signals.services import SignalParsingService
from apps.signals.serializers import SignalSummarySerializer
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
                
            # Parse insights into signals
            signals = SignalParsingService.parse_insights(
                insights=insights,
                account=account,
                source='transcript_analysis',
                user=request.user
            )
            
            # Return signals for user validation
            signal_serializer = SignalSummarySerializer(
                signals, 
                many=True,
                context={'request': request, 'client_id': self.get_client_id()}
            )
            
            # Group signals by category for better UX
            signals_by_category = {}
            for signal in signals:
                category = signal.get_category_display()
                if category not in signals_by_category:
                    signals_by_category[category] = []
                signals_by_category[category].append(
                    SignalSummarySerializer(
                        signal, 
                        context={'request': request, 'client_id': self.get_client_id()}
                    ).data
                )
            
            
            return Response({
                'success': True,
                'signals_count': len(signals),
                'signals': signal_serializer.data,
                'signals_by_category': signals_by_category,
                # Include raw insights for debugging during development
                'raw_insights': insights if settings.DEBUG else None
            }, status=status.HTTP_200_OK)

        except APIError as e:
            raise StandardizedAuthenticationFailed(f"{CoreErrorMessages.SERVICE_AUTH_FAILED} :{str(e)}" )
        except OpenAIError as e:
            raise StandardizedValidationError(f"{CoreErrorMessages.SERVICE_ERROR}: {str(e)}")
        except Exception as e:
            return self.handle_exception(e)

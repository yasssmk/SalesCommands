from rest_framework import status
from django.conf import settings
from rest_framework.response import Response
from openai import OpenAIError, AuthenticationError, APIError
import openai
from core.exceptions import StandardizedValidationError, StandardizedAuthenticationFailed
from core.error_messages import CoreErrorMessages
from .prompts import get_full_insights
from .serializers import TranscriptAnalysisSerializer
from core.apps_shared_methods import BaseAPIView

class TranscriptAnalysisView(BaseAPIView):
    """
    API view for analyzing transcripts using OpenAI.
    Follows the client-scoped architecture and standardized error handling.
    """
    serializer_class = TranscriptAnalysisSerializer
    entity_name = 'transcript'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Initialize OpenAI with error handling
        try:
            api_key = settings.OPENAI_API_KEY["OPENAI_API_KEY"]
            if not api_key:
                raise StandardizedValidationError(CoreErrorMessages.INVALID_CONFIG)
            openai.api_key = api_key
        except Exception as e:
            raise StandardizedValidationError(CoreErrorMessages.SERVICE_UNAVAILABLE)

    def post(self, request, *args, **kwargs):
        """
        Analyze transcript using OpenAI.
        Handles both single and batch analysis requests.
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
            
            # Process through OpenAI

            insights = get_full_insights(transcript)
   
            
            if not insights:
                raise StandardizedValidationError(CoreErrorMessages.PROCESSING_FAILED)

            return Response(insights, status=status.HTTP_200_OK)

        except APIError as e:
            raise StandardizedAuthenticationFailed(f"{CoreErrorMessages.SERVICE_AUTH_FAILED} :{str(e)}" )
        except OpenAIError as e:
            raise StandardizedValidationError(f"{CoreErrorMessages.SERVICE_ERROR}: {str(e)}")
        except Exception as e:
            return self.handle_exception(e)

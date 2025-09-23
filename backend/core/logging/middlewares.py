"""
Logging middlewares for request tracking and correlation.

RequestIdMiddleware must be placed FIRST in MIDDLEWARE settings
to ensure correlation ID is available for all other middlewares.
"""

import logging
import re
import uuid
from django.utils.deprecation import MiddlewareMixin
from django.http import HttpRequest, HttpResponse

from .context import set_correlation_id, get_correlation_id, clear_correlation_id

logger = logging.getLogger(__name__)


class RequestIdMiddleware(MiddlewareMixin):
    """
    Middleware that assigns a unique correlation ID to each request.

    This middleware:
    1. Checks for existing X-Request-ID header from client/proxy
    2. Generates a new UUID if none exists
    3. Stores the ID in contextvars for the request lifecycle
    4. Adds X-Request-ID to the response headers

    MUST be placed FIRST in MIDDLEWARE list.
    """

    # Header names
    REQUEST_ID_HEADER = "HTTP_X_REQUEST_ID"  # Django's internal format
    RESPONSE_HEADER = "X-Request-ID"

    def process_request(self, request: HttpRequest) -> None:
        # 1) read incoming header if any
        correlation_id = None
        incoming_id = request.META.get(self.REQUEST_ID_HEADER)
        if incoming_id and self._is_valid_correlation_id(incoming_id):
            correlation_id = incoming_id
            logger.debug(
                "Using incoming X-Request-ID",
                extra={"correlation_id": correlation_id, "source": "header"},
            )

        # 2) otherwise generate one
        if not correlation_id:
            correlation_id = str(uuid.uuid4())
            logger.debug(
                "Generated new correlation ID",
                extra={"correlation_id": correlation_id, "source": "generated"},
            )

        # 3) store in context + on request
        set_correlation_id(correlation_id)
        request.correlation_id = correlation_id

    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        # 4) add to response header
        correlation_id = get_correlation_id()
        if correlation_id and correlation_id != "-":
            response[self.RESPONSE_HEADER] = correlation_id

        # cleanup (contextvars would auto-clean between requests, but explicit is fine)
        clear_correlation_id()
        return response

    def process_exception(self, request: HttpRequest, exception: Exception) -> None:
        # keep the correlation id available for error logs
        correlation_id = get_correlation_id()
        logger.debug(
            "request_exception",
            extra={"correlation_id": correlation_id, "exception_type": exception.__class__.__name__},
        )
        return None

    def _is_valid_correlation_id(self, correlation_id: str) -> bool:
        if not correlation_id or len(correlation_id) > 128:
            return False
        return bool(re.match(r"^[a-zA-Z0-9\-_]+$", correlation_id))

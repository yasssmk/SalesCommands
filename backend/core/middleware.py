from django.utils.deprecation import MiddlewareMixin


# FOR DEBUGGIN Header purpose, delete file and In settings.py add 'core.middleware.LogRequestHeadersMiddleware' in MIDDLEWARE


class LogRequestHeadersMiddleware(MiddlewareMixin):
    def process_request(self, request):
        print(f"Request Headers: {request.headers}")
        return None
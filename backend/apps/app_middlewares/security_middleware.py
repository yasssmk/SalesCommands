from django.http import HttpResponseForbidden
import re
from urllib.parse import unquote
import json
import base64

class InputSanitizationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        
        self.sql_patterns = [
            # Basic SQL injection
            r"(?i)(\b(select|insert|update|delete|drop|union|exec|declare)\b)",
            r"(?i)((\%27)|(\')|(\-\-)|(\%23)|(#))",
            
            # Advanced SQL injection
            r"(?i)(\bor\b|\band\b)\s*[\'\"]*\s*\w+\s*[=><]",
            r"(?i)\bunion\s+(?:all\s+)?select\b",
            r"(?i)(?:null|true|false|\d+)\s*(?:--|\#|\/\*)",
            r"(?i)(?:benchmark|sleep|delay|waitfor|pg_sleep)",
            r";\s*(?:drop|delete|update|insert|create|alter)",
            r"\/\*.*?\*\/",
            r";\s*$",
            r"--\s*$",
            r"\bxp_cmdshell\b",
            
            # Encoded attacks
            r"(?i)(?:\\x(?:[0-9a-f]{2})){2,}",
            r"(?:%[0-9A-Fa-f]{2}){2,}",
            r"(?:chr|char)\s*\(\s*\d+\s*(?:\s*\+\s*\d+\s*)*\)",
        ]
        
        self.xss_patterns = [
            r"(?i)<[^>]*script.*?>",
            r"(?i)<[^>]*object.*?>",
            r"(?i)<[^>]*iframe.*?>",
            r"(?i)<[^>]*applet.*?>",
            r"(?i)<[^>]*meta.*?>",
            r"(?i)<[^>]*style.*?>",
            r"(?i)<[^>]*form.*?>",
            r"(?i)<[^>]*img.*?onerror.*?>",
            r"(?i)\b(on\w+\s*=)",
            r"(?i)(javascript|vbscript|expression)\s*:",
            r"(?i)document\.",
            r"(?i)eval\s*\(",
        ]
        
        self.sql_regex = [re.compile(pattern, re.IGNORECASE | re.MULTILINE) for pattern in self.sql_patterns]
        self.xss_regex = [re.compile(pattern) for pattern in self.xss_patterns]

    def check_injection(self, value):
        """Enhanced checking with multiple decodings"""
        values_to_check = [
            value,
            unquote(value),
            unquote(unquote(value)),  # Double-decoded
            value.replace('\\', ''),   # Backslash stripped
        ]
        
        # Try base64 decode
        try:
            decoded = base64.b64decode(value).decode('utf-8')
            values_to_check.append(decoded)
        except:
            pass
            
        # Check all variants
        for test_value in values_to_check:
            # Remove common evasion techniques
            cleaned = re.sub(r'\s+', ' ', test_value)  # Normalize whitespace
            cleaned = re.sub(r'/\*.*?\*/', '', cleaned)  # Remove comments
            cleaned = cleaned.lower()  # Case normalization
            
            for pattern in self.sql_regex:
                if pattern.search(cleaned):
                    return True
                    
            for pattern in self.xss_regex:
                if pattern.search(cleaned):
                    return True
        
        return False

    def check_json_data(self, data):
        if isinstance(data, dict):
            return any(self.check_json_data(value) for value in data.values())
        elif isinstance(data, list):
            return any(self.check_json_data(item) for item in data)
        elif isinstance(data, str):
            return self.check_injection(data)
        return False

    def process_request(self, request):
        # Check headers for injection attempts
        # for header, value in request.headers.items():
        #     if self.check_injection(str(value)):
        #         return HttpResponseForbidden("Malicious content detected in headers")

        # Check GET parameters
        if request.GET:
            for key, value in request.GET.items():
                if self.check_injection(str(key)) or self.check_injection(str(value)):
                    return HttpResponseForbidden("Malicious content detected in GET parameters")

        # Check POST/PUT data
        if request.method in ['POST', 'PUT', 'PATCH']:
            if request.content_type == 'application/x-www-form-urlencoded':
                for key, value in request.POST.items():
                    if self.check_injection(str(key)) or self.check_injection(str(value)):
                        return HttpResponseForbidden("Malicious content detected in form data")
            
            elif request.content_type == 'application/json':
                try:
                    json_data = json.loads(request.body.decode('utf-8'))
                    if self.check_json_data(json_data):
                        return HttpResponseForbidden("Malicious content detected in JSON data")
                except json.JSONDecodeError:
                    return HttpResponseForbidden("Invalid JSON data")

        return None

    def __call__(self, request):
        response = self.process_request(request)
        if response:
            return response
        return self.get_response(request)
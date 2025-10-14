# backend/reset_throttle.py
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'salescommands.settings')
django.setup()

from django.core.cache import cache
from core.throttle_enforcer import reset_throttle

# Option 1: Vider tout le cache
cache.clear()
print("✅ Cache cleared")

# Option 2: Reset throttle login pour IPs communes de dev
common_ips = ['127.0.0.1', '::1', 'localhost']
for ip in common_ips:
    reset_throttle('login', ip=ip)
    print(f"✅ Throttle reset for IP: {ip}")

# Option 3: Reset pour des emails de test
test_emails = ['admin@companya.com']
for email in test_emails:
    reset_throttle('login', email=email)
    print(f"✅ Throttle reset for email: {email}")

print("\n🎉 Ready for testing!")
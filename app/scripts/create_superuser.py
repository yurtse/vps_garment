import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

import django
try:
    django.setup()
except Exception as e:
    print("Django setup error:", e)
    sys.exit(1)

from django.contrib.auth import get_user_model
User = get_user_model()

username = os.getenv("DJANGO_SUPERUSER_USERNAME", "admin")
email = os.getenv("DJANGO_SUPERUSER_EMAIL", "admin@example.com")
password = os.getenv("DJANGO_SUPERUSER_PASSWORD", "admin")

if not username:
    print("DJANGO_SUPERUSER_USERNAME is empty; aborting.")
    sys.exit(1)

qs = User.objects.filter(username=username)
if qs.exists():
    u = qs.first()
    u.email = email
    u.is_staff = True
    u.is_superuser = True
    u.set_password(password)
    u.save()
    print("Updated superuser:", username)
else:
    User.objects.create_superuser(username=username, email=email, password=password)
    print("Created superuser:", username)

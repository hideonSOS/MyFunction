import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'MyFunction.settings')
django.setup()

from django.test import Client
from django.conf import settings

print("=== Django Settings ===")
print(f"DEBUG: {settings.DEBUG}")
print(f"ALLOWED_HOSTS: {settings.ALLOWED_HOSTS}")
print()

print("=== Login Test ===")
c = Client(enforce_csrf_checks=False)

# ユーザー一覧確認
from django.contrib.auth.models import User
users = User.objects.all()
print(f"Users in DB: {list(users.values_list('username', flat=True))}")
print()

if users.exists():
    username = users.first().username
    # パスワードなしでforce_login
    c.force_login(users.first())
    print(f"Force login as: {username}")

    r = c.get('/')
    print(f"GET / status: {r.status_code}")

    if r.status_code == 500:
        import traceback
        # コンテキストからエラー取得
        if hasattr(r, 'exc_info') and r.exc_info:
            traceback.print_exception(*r.exc_info)
else:
    print("No users found. Run: python manage.py createsuperuser")

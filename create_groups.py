import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mercado_control.settings')
django.setup()

from django.contrib.auth.models import Group

try:
    admin_delegado, created1 = Group.objects.get_or_create(name='admin_delegado')
    trabajador, created2 = Group.objects.get_or_create(name='trabajador')
    print("✅ Grupos creados: admin_delegado, trabajador")
except Exception as e:
    print(f"❌ Error: {e}")

from django.test import TestCase
from django.contrib.auth.models import Group, User
from django.urls import reverse

from .views import es_super_admin, es_admin_especial, es_administrador, es_trabajador


class PermisosUsuarioTests(TestCase):
    def test_helpers_devuelven_false_para_usuario_none(self):
        self.assertFalse(es_super_admin(None))
        self.assertFalse(es_admin_especial(None))
        self.assertFalse(es_administrador(None))
        self.assertTrue(es_trabajador(None))


class AdminUsuarioFormTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_user(
            username="superadmin",
            email="super@example.com",
            password="12345678",
        )
        self.superuser.is_superuser = True
        self.superuser.is_staff = True
        self.superuser.save()

    def test_crear_usuario_nuevo_sin_error(self):
        self.client.force_login(self.superuser)

        response = self.client.post(
            reverse("admin_usuario_nuevo"),
            {
                "username": "nuevo_usuario",
                "email": "nuevo@example.com",
                "first_name": "Nuevo",
                "last_name": "Usuario",
                "rol": "trabajador",
                "is_active": "1",
                "password": "12345678",
                "password_confirm": "12345678",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(username="nuevo_usuario").exists())

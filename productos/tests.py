from django.test import TestCase
from django.contrib.auth.models import Group, User
from django.urls import reverse

from .models import Producto, Avaria
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


class ConsultarCodigoTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="12345678")

    def test_consultar_codigo_reconoce_productos_existentes_en_tabla_producto(self):
        Producto.objects.create(
            codigo_barra="1234567890123",
            nombre="Leche Entera",
            fecha_vencimiento="2030-12-31",
            cantidad=5,
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("consultar_codigo"), {"codigo": "1234567890123"})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["found"])
        self.assertEqual(response.json()["nombre"], "Leche Entera")


class EditarAvariaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="reportador", password="12345678")
        self.avaria = Avaria.objects.create(
            codigo_barra="1234567890123",
            nombre="Leche vieja",
            tipo_danio="rasgado",
            cantidad=2,
            reportado_por=self.user,
        )

    def test_reportador_puede_editar_una_avaria_pendiente(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("editar_avaria", args=[self.avaria.pk]),
            {
                "codigo_barra": "1234567890123",
                "nombre": "Leche editada",
                "tipo_danio": "mojado",
                "cantidad": "5",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.avaria.refresh_from_db()
        self.assertEqual(self.avaria.nombre, "Leche editada")
        self.assertEqual(self.avaria.cantidad, 5)
        self.assertEqual(self.avaria.tipo_danio, "mojado")

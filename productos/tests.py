from datetime import date, timedelta

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


class AvariasTests(TestCase):
    def setUp(self):
        self.superadmin = User.objects.create_user(username="super", password="12345678", is_superuser=True, is_staff=True)
        self.user = User.objects.create_user(username="tester", password="12345678")
        self.avaria = Avaria.objects.create(
            codigo_barra="1111111111111",
            nombre="Leche dañada",
            tipo_danio="rasgado",
            cantidad=2,
            reportado_por=self.user,
        )

    def test_todos_en_avarias_muestra_todas_las_averias(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("listar_avarias"), {"estado": "all"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Leche dañada")

    def test_super_admin_puede_limpiar_productos_vencidos(self):
        Producto.objects.create(
            codigo_barra="2222222222222",
            nombre="Producto vencido",
            fecha_vencimiento="2000-01-01",
            cantidad=1,
        )

        self.client.force_login(self.superadmin)
        response = self.client.post(reverse("limpiar_productos_vencidos"))

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Producto.objects.filter(codigo_barra="2222222222222").exists())


class RevisarProductoTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="admin", password="12345678", is_staff=True)
        self.producto = Producto.objects.create(
            codigo_barra="9876543210987",
            nombre="Arroz premium",
            fecha_vencimiento="2030-01-01",
            cantidad=3,
        )

    def test_admin_puede_marcar_producto_como_revisado(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("marcar_revisado", args=[self.producto.pk]))

        self.assertEqual(response.status_code, 302)
        self.producto.refresh_from_db()
        self.assertTrue(self.producto.revisado)
        self.assertEqual(self.producto.revisado_por, self.admin)

    def test_dashboard_incluye_estado_de_revision_en_fila_del_producto(self):
        self.producto.revisado = True
        self.producto.revisado_por = self.admin
        self.producto.save()

        self.client.force_login(self.admin)
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-revisado=\"1\"")
        self.assertContains(response, "Revisado")

    def test_dashboard_expone_boton_de_escaneo_para_el_filtro_de_codigo(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="btnScanCodigo"')
        self.assertContains(response, 'data-scan-code="true"')

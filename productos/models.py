from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
import random
from django.utils import timezone as tz
from datetime import timedelta


class Configuracion(models.Model):
    dias_alerta = models.PositiveIntegerField(default=7, verbose_name="Días de alerta antes de vencer")

    class Meta:
        verbose_name = "Configuración"

    def __str__(self):
        return f"Alerta: {self.dias_alerta} días antes"

    @classmethod
    def get_config(cls):
        config, _ = cls.objects.get_or_create(pk=1)
        return config

class CatalogoProducto(models.Model):
    """
    Ficha única por código de barra: nombre + foto.
    Se completa automáticamente desde Open Food Facts, o manualmente
    si la API no tiene el producto. Una vez completada, todos los
    lotes futuros de ese código ya muestran nombre y foto sin pedir nada.
    """
    ORIGEN_CHOICES = [
        ("api",     "Open Food Facts"),
        ("manual",  "Ingresado manualmente"),
    ]

    codigo_barra = models.CharField(max_length=100, unique=True, db_index=True)
    nombre       = models.CharField(max_length=200)
    marca        = models.CharField(max_length=120, blank=True)

    # La foto puede venir de una URL externa (API) o subida por el usuario
    foto_url     = models.URLField(max_length=500, blank=True)   # foto de la API
    foto_archivo = models.ImageField(upload_to="productos_fotos/", blank=True, null=True)  # foto subida manual

    origen       = models.CharField(max_length=10, choices=ORIGEN_CHOICES, default="manual")
    fecha_creado = models.DateTimeField(auto_now_add=True)
    fecha_actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Catálogo de producto"
        verbose_name_plural = "Catálogo de productos"
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.nombre} ({self.codigo_barra})"

    @property
    def foto(self):
        """Devuelve la URL de la foto a mostrar, sea de la API o subida manual."""
        if self.foto_archivo:
            return self.foto_archivo.url
        if self.foto_url:
            return self.foto_url
        return None

class Producto(models.Model):
    codigo_barra = models.CharField(max_length=100, verbose_name="Código de barra")
    nombre = models.CharField(max_length=200, verbose_name="Nombre del producto")
    fecha_vencimiento = models.DateField(verbose_name="Fecha de vencimiento")
    cantidad = models.PositiveIntegerField(default=1, verbose_name="Cantidad en stock")
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Producto"
        ordering = ["fecha_vencimiento"]
        constraints = [
            models.UniqueConstraint(
                fields=['codigo_barra', 'fecha_vencimiento'],
                name='unique_codigo_fecha'
            )
        ]

    def __str__(self):
        return f"{self.nombre} — vence {self.fecha_vencimiento}"

    @property
    def dias_para_vencer(self):
        hoy = timezone.now().date()
        delta = self.fecha_vencimiento - hoy
        return delta.days

    @property
    def estado(self):
        d = self.dias_para_vencer
        config = Configuracion.get_config()
        if d < 0:
            return "vencido"
        elif d <= config.dias_alerta:
            return "alerta"
        else:
            return "ok"

class CodigoRecuperacion(models.Model):
    """
    Guarda un código temporal de 7 dígitos para que un usuario
    pueda recuperar su contraseña por email. Cada código vence
    a los 10 minutos de haberse creado, por seguridad.
    """
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    codigo = models.CharField(max_length=7)
    creado = models.DateTimeField(auto_now_add=True)
    usado = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Código de recuperación"

    def __str__(self):
        return f"{self.usuario.username} — {self.codigo}"

    @classmethod
    def generar_para(cls, usuario):
        """
        Crea un código nuevo de 7 dígitos para este usuario.
        Si ya tenía códigos anteriores sin usar, los invalidamos
        primero (así solo el último código generado es válido).

        Por seguridad, rechazamos códigos donde el mismo dígito se
        repite 3 veces o más (ej: "1112345" o "4455551") — esos son
        mucho más fáciles de adivinar al azar que uno bien distribuido.
        Volvemos a generar hasta conseguir uno aceptable.
        """
        # Invalidamos cualquier código viejo sin usar de este usuario
        cls.objects.filter(usuario=usuario, usado=False).update(usado=True)

        nuevo_codigo = cls._generar_codigo_seguro()
        return cls.objects.create(usuario=usuario, codigo=nuevo_codigo)

    @staticmethod
    def _generar_codigo_seguro():
        """
        Genera un código de 7 dígitos al azar, descartando aquellos
        donde algún dígito aparezca 3 veces o más.
        """
        while True:
            codigo = "".join(random.choices("0123456789", k=7))

            # Contamos cuántas veces aparece el dígito más repetido
            repeticiones = max(codigo.count(d) for d in set(codigo))

            if repeticiones < 3:
                return codigo
            # si no pasó el filtro, el while vuelve a intentar con otro

    @property
    def expirado(self):
        """True si pasaron más de 1 minutos desde que se generó."""
        limite = self.creado + timedelta(minutes=1)
        return tz.now() > limite

    @property
    def valido(self):
        """True si el código no fue usado todavía y no expiró."""
        return not self.usado and not self.expirado    

class Avaria(models.Model):
    """
    Registro de un producto físicamente dañado que debe darse
    de baja del sistema externo del mercado. Es completamente
    independiente del módulo de vencimientos — un producto puede
    estar dañado sin importar su fecha de vencimiento.
    """

    TIPOS_DANIO = [
        ("rasgado",   "Rasgado / embalagem rasgada"),
        ("mojado",    "Molhado / úmido"),
        ("aplastado", "Amassado / deformado"),
        ("vencido",   "Vencido (retirado da gôndola)"),
        ("otro",      "Outro"),
    ]

    ESTADOS = [
        ("pendiente", "Pendente de baixa"),
        ("cerrado",   "Fechado / dado baixa"),
    ]

    # Datos del producto
    codigo_barra = models.CharField(max_length=100, verbose_name="Código de barras")
    nombre       = models.CharField(max_length=200, verbose_name="Nome do produto")

    # Datos de la avaria
    tipo_danio   = models.CharField(max_length=20, choices=TIPOS_DANIO, verbose_name="Tipo de avaria")
    cantidad     = models.PositiveIntegerField(default=1, verbose_name="Quantidade")
    estado       = models.CharField(max_length=20, choices=ESTADOS, default="pendiente", verbose_name="Estado")

    # Trazabilidad
    reportado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="avarias_reportadas",
        verbose_name="Reportado por",
    )
    fecha_reporte = models.DateTimeField(auto_now_add=True, verbose_name="Data do reporte")

    cerrado_por   = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="avarias_cerradas",
        verbose_name="Fechado por",
    )
    fecha_cierre  = models.DateTimeField(null=True, blank=True, verbose_name="Data de fechamento")

    class Meta:
        ordering = ["-fecha_reporte"]
        verbose_name = "Avaria"
        verbose_name_plural = "Avarias"

    def __str__(self):
        return f"{self.nombre} — {self.get_tipo_danio_display()} — {self.estado}"

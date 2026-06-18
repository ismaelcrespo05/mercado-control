from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User


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


class ProductoDañado(models.Model):
    TIPO_DANIO_CHOICES = [
        ('RASGADO', 'Rasgado'),
        ('ROTO', 'Roto'),
        ('ECHADO_PERDER', 'Echado a perder'),
        ('MOJADO', 'Mojado'),
        ('OTRO', 'Otro'),
    ]
    
    ESTADO_CHOICES = [
        ('REPORTADO', 'Reportado'),
        ('REVISADO', 'Revisado'),
        ('DESCARTADO', 'Descartado'),
    ]
    
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, verbose_name="Producto")
    tipo_danio = models.CharField(max_length=20, choices=TIPO_DANIO_CHOICES, verbose_name="Tipo de daño")
    motivo = models.TextField(verbose_name="Motivo/Descripción", blank=True)
    fecha_reporte = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de reporte")
    reportado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="Reportado por")
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='REPORTADO', verbose_name="Estado")
    
    class Meta:
        verbose_name = "Producto Dañado"
        verbose_name_plural = "Productos Dañados"
        ordering = ["-fecha_reporte"]
    
    def __str__(self):
        return f"{self.producto.nombre} - {self.tipo_danio} ({self.fecha_reporte.strftime('%d/%m/%Y')})"

from django.db import models
from django.utils import timezone


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

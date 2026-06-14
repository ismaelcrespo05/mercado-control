from django.contrib import admin
from .models import Producto, Configuracion, ProductoDañado

@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'codigo_barra', 'fecha_vencimiento', 'cantidad')
    list_filter = ('fecha_vencimiento',)
    search_fields = ('nombre', 'codigo_barra')

@admin.register(Configuracion)
class ConfiguracionAdmin(admin.ModelAdmin):
    list_display = ('dias_alerta',)

@admin.register(ProductoDañado)
class ProductoDañadoAdmin(admin.ModelAdmin):
    list_display = ('producto', 'tipo_danio', 'estado', 'fecha_reporte', 'reportado_por')
    list_filter = ('tipo_danio', 'estado', 'fecha_reporte')
    search_fields = ('producto__nombre', 'motivo')
    readonly_fields = ('fecha_reporte', 'reportado_por')

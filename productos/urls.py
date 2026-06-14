from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("escanear/", views.escanear, name="escanear"),
    path("buscar-codigo/", views.buscar_codigo, name="buscar_codigo"),
    path("vender/<int:pk>/", views.vender, name="vender"),
    path("eliminar/<int:pk>/", views.eliminar, name="eliminar"),
    path("configuracion/", views.configuracion, name="configuracion"),
]

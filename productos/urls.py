from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("escanear/", views.escanear, name="escanear"),
    path("buscar-codigo/", views.buscar_codigo, name="buscar_codigo"),
    path("buscar-productos/", views.buscar_productos, name="buscar_productos"),
    path("editar/<int:pk>/", views.editar_producto, name="editar"),
    path("vender/<int:pk>/", views.vender, name="vender"),
    path("eliminar/<int:pk>/", views.eliminar, name="eliminar"),
    path("reportar-danio/<int:pk>/", views.reportar_danio, name="reportar_danio"),
    path("danios/", views.listar_danios, name="listar_danios"),
    path("revisar-danio/<int:pk>/", views.revisar_danio, name="revisar_danio"),
    path("configuracion/", views.configuracion, name="configuracion"),
]

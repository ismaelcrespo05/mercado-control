from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("admin/", views.admin_panel, name="admin_panel"),
    path("admin/usuarios/nuevo/", views.admin_usuario_form, name="admin_usuario_nuevo"),
    path("admin/usuarios/<int:pk>/editar/", views.admin_usuario_form, name="admin_usuario_editar"),
    path("admin/usuarios/<int:pk>/eliminar/", views.admin_usuario_eliminar, name="admin_usuario_eliminar"),
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
    path("consultar-codigo/",     views.consultar_codigo,      name="consultar_codigo"),
    path("guardar-ficha-manual/", views.guardar_ficha_manual,  name="guardar_ficha_manual"),
    path("consultar-codigo/",     views.consultar_codigo,      name="consultar_codigo"),
    path("guardar-ficha-manual/", views.guardar_ficha_manual,  name="guardar_ficha_manual"),
    path("galeria/",              views.galeria_productos,     name="galeria_productos"),

]

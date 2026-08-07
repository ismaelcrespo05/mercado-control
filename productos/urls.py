from django.urls import path
from . import views # el . hace que importe views.py que estan en esta misma carpeta

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
    path("marcar-revisado/<int:pk>/", views.marcar_revisado, name="marcar_revisado"),

    path("eliminar/<int:pk>/", views.eliminar, name="eliminar"),
    path("configuracion/", views.configuracion, name="configuracion"),
    path("consultar-codigo/",     views.consultar_codigo,      name="consultar_codigo"),
    path("guardar-ficha-manual/", views.guardar_ficha_manual,  name="guardar_ficha_manual"),
    path("buscar-por-nombre/",   views.buscar_por_nombre,    name="buscar_por_nombre"),
    path("importar-externa/",    views.importar_de_externa,  name="importar_de_externa"),
    path("buscador/",            views.pagina_buscador,      name="pagina_buscador"),
    path("cambiar-password/",      views.cambiar_password,       name="cambiar_password"),
    path("recuperar/",              views.solicitar_recuperacion, name="solicitar_recuperacion"),
    path("recuperar/verificar/",    views.verificar_codigo,       name="verificar_codigo"),
    path("avarias/",                  views.listar_avarias,   name="listar_avarias"),
    path("avarias/reportar/",         views.reportar_avaria,  name="reportar_avaria"),
    path("avarias/editar/<int:pk>/",  views.editar_avaria,    name="editar_avaria"),
    path("avarias/cerrar/<int:pk>/",  views.cerrar_avaria,    name="cerrar_avaria"),
    path("avarias/limpiar-vencidos/", views.limpiar_productos_vencidos, name="limpiar_productos_vencidos"),

]

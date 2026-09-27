from django.urls import path, include
from django.views.i18n import JavaScriptCatalog
from django.conf import settings
from django.conf.urls.static import static
from django.views.i18n import set_language

urlpatterns = [
    path("", include("productos.urls")),
    path("i18n/setlang/", set_language, name="set_language"),
    path("i18n/catalog.js", JavaScriptCatalog.as_view(domain="django"), name="javascript-catalog"),
]

# Esto le dice a Django: "mientras estás en desarrollo o en PythonAnywhere
# sin un servidor de archivos dedicado, serví las fotos subidas desde
# /media/ usando esta misma app". Sin esto, las URLs de las fotos
# devuelven error 404 aunque el archivo exista en el disco.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

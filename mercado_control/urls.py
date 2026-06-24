from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("", include("productos.urls")),
]

# Esto le dice a Django: "mientras estás en desarrollo o en PythonAnywhere
# sin un servidor de archivos dedicado, serví las fotos subidas desde
# /media/ usando esta misma app". Sin esto, las URLs de las fotos
# devuelven error 404 aunque el archivo exista en el disco.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

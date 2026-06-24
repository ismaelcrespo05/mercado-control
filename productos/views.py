from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import Group, User
from django.db.models import Count
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from .models import Producto, Configuracion, ProductoDañado
import json
from django.utils import timezone
from datetime import timedelta
from .models import CatalogoProducto
from .servicios import buscar_en_openfoodfacts

ROLES_GESTIONABLES = {
    "admin": "Administrador",
    "admin_delegado": "Admin delegado",
    "trabajador": "Trabajador",
}


def es_admin(user):
    return user.is_staff


def es_admin_delegado(user):
    return user.groups.filter(name='admin_delegado').exists()


def es_trabajador(user):
    return user.groups.filter(name='trabajador').exists()


def puede_editar(user):
    return user.is_staff or es_admin_delegado(user)


def puede_eliminar(user):
    return user.is_staff


def asegurar_grupos():
    grupos = {}
    for nombre in ("admin_delegado", "trabajador"):
        grupos[nombre], _ = Group.objects.get_or_create(name=nombre)
    return grupos


def rol_usuario(user):
    if user.is_staff:
        return "admin", "Administrador"
    if user.groups.filter(name="admin_delegado").exists():
        return "admin_delegado", "Admin delegado"
    if user.groups.filter(name="trabajador").exists():
        return "trabajador", "Trabajador"
    return "sin_rol", "Sin rol"


def aplicar_rol(user, rol):
    grupos = asegurar_grupos()
    user.is_staff = rol == "admin"

    if not user.pk:
        return

    user.groups.remove(*grupos.values())
    if rol in grupos:
        user.groups.add(grupos[rol])


def hay_otro_admin_activo(user):
    return User.objects.filter(is_staff=True, is_active=True).exclude(pk=user.pk).exists()


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f"Bienvenido, {user.first_name or user.username}!")
            return redirect('dashboard')
        else:
            messages.error(request, "Usuario o contraseña incorrectos.")
    
    return render(request, "productos/login.html")


def logout_view(request):
    logout(request)
    messages.info(request, "Sesión cerrada correctamente.")
    return redirect('login')


@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard')
def admin_panel(request):
    asegurar_grupos()
    hoy = timezone.now().date()
    config = Configuracion.get_config()
    productos = Producto.objects.all()

    vencidos  = sum(1 for p in productos if p.dias_para_vencer < 0)
    en_alerta = sum(1 for p in productos if 0 <= p.dias_para_vencer <=config.dias_alerta)
    ok        = sum(1 for p in productos if p.dias_para_vencer > config.dias_alerta)

    danios_recientes = ProductoDañado.objects.select_related('producto', 'reportado_por').order_by('-fecha_reporte')[:10]
    danios_por_tipo  = ProductoDañado.objects.values('tipo_danio').annotate(total=Count('id')).order_by('-total')

    usuarios = User.objects.prefetch_related("groups").order_by("username")
    usuarios_con_roles = [
        {
            "usuario": usuario,
            "rol_codigo": rol_usuario(usuario)[0],
            "rol_nombre": rol_usuario(usuario)[1],
        }
        for usuario in usuarios
    ]

    return render(request, "productos/admin_panel.html", {
        "usuarios_con_roles": usuarios_con_roles,
        "total_usuarios": usuarios.count(),
        "usuarios_activos": usuarios.filter(is_active=True).count(),
        "total_productos": Producto.objects.count(),
        "danios_pendientes": ProductoDañado.objects.filter(estado="REPORTADO").count(),
        "vencidos": vencidos,
        "en_alerta": en_alerta,
        "ok": ok,
        "config": config,
        "danios_recientes": danios_recientes,
        "danios_por_tipo": danios_por_tipo,
    })
    

@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard')
def admin_usuario_form(request, pk=None):
    asegurar_grupos()
    usuario = get_object_or_404(User, pk=pk) if pk else None
    es_edicion = usuario is not None
    rol_actual = rol_usuario(usuario)[0] if usuario else "trabajador"

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        email = request.POST.get("email", "").strip()
        rol = request.POST.get("rol", "trabajador").strip()
        is_active = request.POST.get("is_active", "1") == "1"
        password = request.POST.get("password", "")
        password_confirm = request.POST.get("password_confirm", "")

        if not username:
            messages.error(request, "El usuario es obligatorio.")
        elif rol not in ROLES_GESTIONABLES:
            messages.error(request, "Selecciona un rol válido.")
        elif not es_edicion and not password:
            messages.error(request, "La contraseña es obligatoria para usuarios nuevos.")
        elif password and password != password_confirm:
            messages.error(request, "Las contraseñas no coinciden.")
        elif User.objects.filter(username=username).exclude(pk=usuario.pk if usuario else None).exists():
            messages.error(request, "Ya existe un usuario con ese nombre.")
        elif es_edicion and usuario == request.user and (rol != "admin" or not is_active):
            messages.error(request, "No puedes quitarte tu propio acceso de administrador.")
        elif es_edicion and not hay_otro_admin_activo(usuario) and (rol != "admin" or not is_active):
            messages.error(request, "Debe quedar al menos un administrador activo.")
        else:
            if not usuario:
                usuario = User(username=username)

            usuario.username = username
            usuario.first_name = first_name
            usuario.last_name = last_name
            usuario.email = email
            usuario.is_active = is_active
            aplicar_rol(usuario, rol)

            if password:
                usuario.set_password(password)

            usuario.save()
            aplicar_rol(usuario, rol)
            usuario.save(update_fields=["is_staff"])
            messages.success(request, "Usuario guardado correctamente.")
            return redirect("admin_panel")

        rol_actual = rol

    return render(request, "productos/admin_usuario_form.html", {
        "usuario_obj": usuario,
        "es_edicion": es_edicion,
        "roles": ROLES_GESTIONABLES.items(),
        "rol_actual": rol_actual,
    })


@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard')
def admin_usuario_eliminar(request, pk):
    usuario = get_object_or_404(User, pk=pk)

    if request.method != "POST":
        return redirect("admin_panel")

    if usuario == request.user:
        messages.error(request, "No puedes eliminar tu propia cuenta.")
    elif usuario.is_staff and not hay_otro_admin_activo(usuario):
        messages.error(request, "Debe quedar al menos un administrador activo.")
    else:
        username = usuario.username
        usuario.delete()
        messages.info(request, f"Usuario '{username}' eliminado.")

    return redirect("admin_panel")


@login_required(login_url='login')
def dashboard(request):
    config = Configuracion.get_config()
    hoy = timezone.now().date()

    # Filtros
    productos = Producto.objects.all()
    
    nombre_filter = request.GET.get('nombre', '').strip()
    codigo_filter = request.GET.get('codigo', '').strip()
    fecha_desde = request.GET.get('fecha_desde', '').strip()
    fecha_hasta = request.GET.get('fecha_hasta', '').strip()
    
    if nombre_filter:
        productos = productos.filter(nombre__icontains=nombre_filter)
    if codigo_filter:
        productos = productos.filter(codigo_barra__icontains=codigo_filter)
    if fecha_desde:
        productos = productos.filter(fecha_vencimiento__gte=fecha_desde)
    if fecha_hasta:
        productos = productos.filter(fecha_vencimiento__lte=fecha_hasta)

    vencidos = [p for p in productos if p.dias_para_vencer < 0]
    en_alerta = [p for p in productos if 0 <= p.dias_para_vencer <= config.dias_alerta]
    ok = [p for p in productos if p.dias_para_vencer > config.dias_alerta]

    return render(request, "productos/dashboard.html", {
        "config": config,
        "vencidos": vencidos,
        "en_alerta": en_alerta,
        "ok": ok,
        "hoy": hoy,
        "nombre_filter": nombre_filter,
        "codigo_filter": codigo_filter,
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta,
        "can_edit": puede_editar(request.user),
    })


@login_required(login_url='login')
def escanear(request):
    if request.method == "POST":
        codigo    = request.POST.get("codigo_barra", "").strip()
        nombre    = request.POST.get("nombre", "").strip()
        fecha_str = request.POST.get("fecha_vencimiento", "").strip()
        foto_manual = request.FILES.get("foto_manual")

        if not codigo.isdigit():
            messages.error(request, "El código de barra solo puede contener números.")
            return render(request, "productos/escanear.html")

        try:
            cantidad = int(request.POST.get("cantidad", 1))
            if cantidad <= 0:
                messages.error(request, "La cantidad debe ser mayor a 0.")
                return render(request, "productos/escanear.html")
        except ValueError:
            messages.error(request, "Cantidad inválida.")
            return render(request, "productos/escanear.html")

        if codigo and nombre and fecha_str:
            try:
                from datetime import date
                año, mes, dia = fecha_str.split("-")
                fecha = date(int(año), int(mes), int(dia))
            except (ValueError, IndexError):
                messages.error(request, "Formato de fecha inválido.")
                return render(request, "productos/escanear.html")

            # Aseguramos que el catálogo tenga la ficha de este producto.
            # Si ya existe (vino de la API o de un registro anterior), no la tocamos
            # salvo que el usuario haya subido una foto manual nueva.
            ficha, creada = CatalogoProducto.objects.get_or_create(
                codigo_barra=codigo,
                defaults={"nombre": nombre, "origen": "manual"},
            )
            if foto_manual:
                ficha.foto_archivo = foto_manual
                ficha.save()

            # Stock real: igual que antes, suma cantidad si ya existe ese lote
            existente = Producto.objects.filter(
                codigo_barra=codigo, fecha_vencimiento=fecha
            ).first()

            if existente:
                existente.cantidad += cantidad
                existente.save()
                messages.success(request, f"Stock actualizado: {existente.nombre} ahora tiene {existente.cantidad} unidades.")
            else:
                Producto.objects.create(
                    codigo_barra=codigo,
                    nombre=nombre,
                    fecha_vencimiento=fecha,
                    cantidad=cantidad,
                )
                messages.success(request, f"Producto '{nombre}' registrado con éxito.")

            return redirect("dashboard")
        else:
            messages.error(request, "Todos los campos son obligatorios.")

    return render(request, "productos/escanear.html")



@login_required(login_url='login')
def buscar_productos(request):
    """AJAX: busca productos para autocompletado."""
    query = request.GET.get("q", "").strip()
    if not query or len(query) < 1:
        return JsonResponse([])
    
    productos = Producto.objects.all()
    
    # Búsqueda por código exacto
    if query.isdigit():
        productos = productos.filter(codigo_barra=query)[:10]
    else:
        # Búsqueda por iniciales o nombre parcial
        productos = productos.filter(nombre__icontains=query)[:10]
    
    resultado = [
        {
            'id': p.id,
            'nombre': p.nombre,
            'codigo': p.codigo_barra,
            'fecha_venc': str(p.fecha_vencimiento),
        }
        for p in productos
    ]
    
    return JsonResponse(resultado, safe=False)


@login_required(login_url='login')
def buscar_codigo(request):
    """AJAX: busca productos previos con ese código para autocompletar nombre."""
    codigo = request.GET.get("codigo", "")
    producto = Producto.objects.filter(codigo_barra=codigo).order_by("-fecha_registro").first()
    if producto:
        return JsonResponse({"found": True, "nombre": producto.nombre})
    return JsonResponse({"found": False})


@login_required(login_url='login')
@user_passes_test(puede_editar, login_url='dashboard')
def editar_producto(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    
    if request.method == "POST":
        codigo = request.POST.get("codigo_barra", "").strip()
        nombre = request.POST.get("nombre", "").strip()
        fecha_str = request.POST.get("fecha_vencimiento", "").strip()
        
        try:
            cantidad = int(request.POST.get("cantidad", 1))
            if cantidad <= 0:
                messages.error(request, "La cantidad debe ser mayor a 0.")
                return render(request, "productos/editar_producto.html", {"producto": producto})
        except ValueError:
            messages.error(request, "Cantidad inválida.")
            return render(request, "productos/editar_producto.html", {"producto": producto})
        
        if codigo and nombre and fecha_str:
            try:
                from datetime import date
                año, mes, dia = fecha_str.split("-")
                fecha = date(int(año), int(mes), int(dia))
            except (ValueError, IndexError):
                messages.error(request, "Formato de fecha inválido.")
                return render(request, "productos/editar_producto.html", {"producto": producto})
            
            producto.codigo_barra = codigo
            producto.nombre = nombre
            producto.fecha_vencimiento = fecha
            producto.cantidad = cantidad
            producto.save()
            
            messages.success(request, f"Producto '{nombre}' actualizado correctamente.")
            return redirect("dashboard")
        else:
            messages.error(request, "Todos los campos son obligatorios.")
    
    return render(request, "productos/editar_producto.html", {"producto": producto})


@login_required(login_url='login')
def vender(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    if request.method == "POST":
        try:
            cantidad_venta = int(request.POST.get("cantidad", 1))
            if cantidad_venta <= 0:
                messages.error(request, "La cantidad debe ser mayor a 0.")
                return render(request, "productos/vender.html", {"producto": producto})
        except ValueError:
            messages.error(request, "Cantidad inválida. Debe ser un número entero.")
            return render(request, "productos/vender.html", {"producto": producto})
        
        # Validar que no se venda más de lo que hay
        if cantidad_venta <= producto.cantidad:
            if cantidad_venta == producto.cantidad:
                producto.delete()
                messages.info(request, "Producto agotado y eliminado del stock.")
            else:
                producto.cantidad -= cantidad_venta
                producto.save()
                messages.success(request, f"Venta registrada. Quedan {producto.cantidad} unidades.")
        else:
            messages.error(request, f"Stock insuficiente. Disponibles: {producto.cantidad} unidades.")
            return render(request, "productos/vender.html", {"producto": producto})
        
        return redirect("dashboard")
    return render(request, "productos/vender.html", {"producto": producto})


@login_required(login_url='login')
@user_passes_test(puede_eliminar, login_url='dashboard')
def eliminar(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    if request.method == "POST":
        nombre = producto.nombre
        producto.delete()
        messages.info(request, f"'{nombre}' eliminado.")
    return redirect("dashboard")


@login_required(login_url='login')
def reportar_danio(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    
    if request.method == "POST":
        tipo_danio = request.POST.get("tipo_danio", "").strip()
        motivo = request.POST.get("motivo", "").strip()
        
        if tipo_danio:
            ProductoDañado.objects.create(
                producto=producto,
                tipo_danio=tipo_danio,
                motivo=motivo,
                reportado_por=request.user,
            )
            messages.success(request, "Daño reportado correctamente.")
            return redirect("dashboard")
        else:
            messages.error(request, "Debes seleccionar un tipo de daño.")
    
    return render(request, "productos/reportar_danio.html", {"producto": producto})


@login_required(login_url='login')
def listar_danios(request):
    danios = ProductoDañado.objects.all()
    
    # Filtros
    estado_filter = request.GET.get('estado', '').strip()
    tipo_filter = request.GET.get('tipo', '').strip()
    
    if estado_filter:
        danios = danios.filter(estado=estado_filter)
    if tipo_filter:
        danios = danios.filter(tipo_danio=tipo_filter)
    
    return render(request, "productos/danios.html", {
        "danios": danios,
        "estado_filter": estado_filter,
        "tipo_filter": tipo_filter,
    })


@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard')
def revisar_danio(request, pk):
    danio = get_object_or_404(ProductoDañado, pk=pk)
    
    if request.method == "POST":
        nuevo_estado = request.POST.get("estado", "").strip()
        if nuevo_estado in dict(ProductoDañado.ESTADO_CHOICES):
            danio.estado = nuevo_estado
            danio.save()
            messages.success(request, "Estado del daño actualizado.")
            return redirect("listar_danios")
    
    return render(request, "productos/revisar_danio.html", {"danio": danio})


@login_required(login_url='login')
def configuracion(request):
    config = Configuracion.get_config()
    if request.method == "POST":
        dias = int(request.POST.get("dias_alerta", 7))
        config.dias_alerta = dias
        config.save()
        messages.success(request, f"Alerta configurada a {dias} días.")
        return redirect("dashboard")
    return render(request, "productos/configuracion.html", {"config": config})
# ─────────────────────────────────────────────────────────────



# 2) NUEVA VISTA — reemplaza la lógica del paso "escanear código"
#    Esta vista se llama por AJAX cuando el usuario escribe/escanea el código,
#    ANTES de mostrar el resto del formulario.

@login_required(login_url='login')
def consultar_codigo(request):
    """
    Paso 1 del flujo de escaneo.
    Recibe el código de barra y responde con lo que ya sabemos de él:

    1. Si está en nuestro CatalogoProducto -> devuelve nombre y foto guardados.
    2. Si no está, busca en Open Food Facts -> si lo encuentra, lo GUARDA
       en el catálogo para la próxima vez, y devuelve nombre y foto.
    3. Si no está en ningún lado -> devuelve found=False para que el
       formulario pida nombre y foto manualmente.
    """
    codigo = request.GET.get("codigo", "").strip()

    if not codigo or not codigo.isdigit():
        return JsonResponse({"found": False, "error": "codigo_invalido"})

    # 1. Buscar primero en nuestro propio catálogo (rápido, sin internet)
    ficha = CatalogoProducto.objects.filter(codigo_barra=codigo).first()
    if ficha:
        return JsonResponse({
            "found": True,
            "nombre": ficha.nombre,
            "marca": ficha.marca,
            "foto": ficha.foto or "",
            "origen": ficha.origen,
        })

    # 2. No está en nuestro catálogo: preguntar a Open Food Facts
    resultado_api = buscar_en_openfoodfacts(codigo)

    if resultado_api:
        # Lo guardamos para que la próxima vez ya esté en nuestro catálogo
        ficha = CatalogoProducto.objects.create(
            codigo_barra=codigo,
            nombre=resultado_api["nombre"],
            marca=resultado_api["marca"],
            foto_url=resultado_api["foto_url"],
            origen="api",
        )
        return JsonResponse({
            "found": True,
            "nombre": ficha.nombre,
            "marca": ficha.marca,
            "foto": ficha.foto or "",
            "origen": "api",
        })

    # 3. No se encontró en ningún lado: el formulario pedirá los datos a mano
    return JsonResponse({"found": False})


@login_required(login_url='login')
def guardar_ficha_manual(request):
    """
    Cuando un código no se encontró ni en el catálogo propio ni en
    Open Food Facts, el usuario completa nombre y (opcional) foto.
    Esta vista guarda esa ficha para que el próximo escaneo de ese
    código ya la reconozca automáticamente.
    """
    if request.method != "POST":
        return JsonResponse({"ok": False}, status=405)

    codigo = request.POST.get("codigo_barra", "").strip()
    nombre = request.POST.get("nombre", "").strip()
    foto   = request.FILES.get("foto")  # puede venir vacío, es opcional

    if not codigo or not nombre:
        return JsonResponse({"ok": False, "error": "datos_incompletos"})

    ficha, creada = CatalogoProducto.objects.get_or_create(
        codigo_barra=codigo,
        defaults={"nombre": nombre, "origen": "manual"},
    )
    if not creada:
        ficha.nombre = nombre  # permite corregir el nombre si ya existía

    if foto:
        ficha.foto_archivo = foto

    ficha.save()

    return JsonResponse({
        "ok": True,
        "nombre": ficha.nombre,
        "foto": ficha.foto or "",
    })
    
@login_required(login_url='login')
def galeria_productos(request):
    """
    Muestra todas las fichas del catálogo (CatalogoProducto) con su foto,
    sin importar el stock actual. Es la "biblioteca visual" de todo lo
    que el mercado ha registrado alguna vez.
    """
    busqueda = request.GET.get("q", "").strip()

    fichas = CatalogoProducto.objects.all().order_by("nombre")

    if busqueda:
        fichas = fichas.filter(nombre__icontains=busqueda)

    # Separamos las que tienen foto de las que no, para mostrar
    # primero las que sí tienen imagen (más útil visualmente)
    con_foto = [f for f in fichas if f.foto]
    sin_foto = [f for f in fichas if not f.foto]

    return render(request, "productos/galeria.html", {
        "con_foto": con_foto,
        "sin_foto": sin_foto,
        "busqueda": busqueda,
        "total": fichas.count(),
    })
    


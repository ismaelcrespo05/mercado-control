from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import Group, User
from django.db.models import Count
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from .models import Producto, Configuracion, CatalogoProducto, Avaria, CodigoRecuperacion
import json
from datetime import timedelta
from .servicios import buscar_en_openfoodfacts, buscar_por_nombre_openfoodfacts
from django.core.mail import send_mail
from django.contrib.auth import update_session_auth_hash

ROLES_GESTIONABLES = {
    "admin_especial": "Administrador Especial",
    "administrador": "Administrador",
    "trabajador": "Trabajador",
}


def es_super_admin(user):
    """True solo para el único Super Admin del sistema. Es is_superuser de Django."""
    return user.is_superuser


def es_admin_especial(user):
    """True si pertenece al grupo 'admin_especial'."""
    return user.groups.filter(name="admin_especial").exists()


def es_administrador(user):
    """True si pertenece al grupo 'administrador' (rol normal, no el especial)."""
    return user.groups.filter(name="administrador").exists()


def es_trabajador(user):
    """True si no tiene ninguno de los 3 roles de arriba."""
    return not (es_super_admin(user) or es_admin_especial(user) or es_administrador(user))


def puede_gestionar_usuarios(user):
    """
    True si el usuario puede ENTRAR a las pantallas de crear/eliminar
    usuarios (sin importar todavía a quién le toque o no). Se usa en
    los decoradores @user_passes_test de las vistas.
    """
    return es_super_admin(user) or es_admin_especial(user) or es_administrador(user)


def puede_editar(user):
    """Quién puede editar productos: todos excepto el Trabajador."""
    return not es_trabajador(user)


def puede_eliminar_producto(user):
    """Quién puede eliminar PRODUCTOS (no usuarios): todos excepto Trabajador."""
    return not es_trabajador(user)


def asegurar_grupos():
    """
    Crea los grupos 'admin_especial' y 'administrador' si todavía no
    existen. Segura de llamar muchas veces (no duplica).
    """
    grupos = {}
    for nombre in ("admin_especial", "administrador"):
        grupos[nombre], _ = Group.objects.get_or_create(name=nombre)
    return grupos


def rol_usuario(user):
    """Devuelve (codigo, nombre_visible) del rol actual de un usuario."""
    if es_super_admin(user):
        return "super_admin", "Super Administrador"
    if es_admin_especial(user):
        return "admin_especial", "Administrador Especial"
    if es_administrador(user):
        return "administrador", "Administrador"
    return "trabajador", "Trabajador"


def aplicar_rol(user, rol):
    """
    Asigna el rol indicado (string: "admin_especial", "administrador"
    o "trabajador") sacando al usuario de cualquier otro grupo antes.
    El Super Admin se maneja aparte, nunca con esta función.
    """
    grupos = asegurar_grupos()

    if not user.pk:
        return  # el usuario todavía no fue guardado, no se le pueden tocar grupos

    user.groups.remove(*grupos.values())

    if rol in grupos:
        user.groups.add(grupos[rol])


def roles_que_puede_asignar(quien_crea):
    """
    Devuelve la lista de roles que ESTA persona puede asignarle a
    un usuario nuevo o existente, según la jerarquía:
      - Super Admin o Admin Especial -> puede asignar admin_especial,
        administrador o trabajador
      - Administrador normal -> solo puede asignar trabajador
    """
    if es_super_admin(quien_crea) or es_admin_especial(quien_crea):
        return ["admin_especial", "administrador", "trabajador"]
    return ["trabajador"]


def puede_eliminar_a(quien_elimina, a_quien):
    """
    Jerarquía completa de 4 roles para decidir si 'quien_elimina'
    puede borrar la cuenta de 'a_quien'. Se evalúa de la regla más
    restrictiva a la más permisiva; la primera que aplique decide.
    """
    # Nadie puede eliminar al Super Admin. Sin excepciones.
    if es_super_admin(a_quien):
        return False

    # El Super Admin puede eliminar a cualquiera que no sea
    # otro Super Admin (ya descartado arriba)
    if es_super_admin(quien_elimina):
        return True

    # Solo el Super Admin puede eliminar a un Admin Especial.
    # Si llegamos aquí, quien_elimina YA NO es Super Admin.
    if es_admin_especial(a_quien):
        return False

    # El Admin Especial puede eliminar Administradores y Trabajadores
    if es_admin_especial(quien_elimina):
        return True

    # Un Administrador normal solo puede eliminar Trabajadores
    if es_administrador(quien_elimina):
        return es_trabajador(a_quien)

    # Cualquier otro caso (Trabajador intentando eliminar) -> no
    return False


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
@user_passes_test(puede_gestionar_usuarios, login_url='dashboard')
def admin_panel(request):
    asegurar_grupos()
    hoy = timezone.now().date()
    config = Configuracion.get_config()
    productos = Producto.objects.all()

    vencidos  = sum(1 for p in productos if p.dias_para_vencer < 0)
    en_alerta = sum(1 for p in productos if 0 <= p.dias_para_vencer <=config.dias_alerta)
    ok        = sum(1 for p in productos if p.dias_para_vencer > config.dias_alerta)


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
        "vencidos": vencidos,
        "en_alerta": en_alerta,
        "ok": ok,
        "config": config
    })
    
@login_required(login_url='login')
@user_passes_test(puede_gestionar_usuarios, login_url='dashboard')
def admin_usuario_form(request, pk=None):
    asegurar_grupos()

    usuario = User.objects.filter(pk=pk).first() if pk else None
    if pk and usuario is None:
        messages.info(request, "Ese usuario ya no existe o fue eliminado.")
        return redirect("admin_panel")

    es_edicion = usuario is not None
    rol_actual = rol_usuario(usuario)[0] if usuario else "trabajador"

    # Roles que ESTA persona logueada puede asignar
    roles_disponibles = roles_que_puede_asignar(request.user)

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        email = request.POST.get("email", "").strip()
        rol = request.POST.get("rol", "trabajador").strip()
        is_active = request.POST.get("is_active", "1") == "1"
        password = request.POST.get("password", "")
        password_confirm = request.POST.get("password_confirm", "")

        # Verificación de seguridad real: el rol pedido tiene que estar
        # entre los que esta persona puede asignar, sin importar lo
        # que muestre el HTML del formulario
        if rol not in roles_disponibles:
            messages.error(request, "No tenés permiso para asignar ese rol.")
            return redirect("admin_panel")

        if not username:
            messages.error(request, "El usuario es obligatorio.")
        elif not es_edicion and not password:
            messages.error(request, "La contraseña es obligatoria para usuarios nuevos.")
        elif password and password != password_confirm:
            messages.error(request, "Las contraseñas no coinciden.")
        elif User.objects.filter(username=username).exclude(pk=usuario.pk if usuario else None).exists():
            messages.error(request, "Ya existe un usuario con ese nombre.")
        else:
            if not usuario:
                usuario = User(username=username)

            usuario.username = username
            usuario.first_name = first_name
            usuario.last_name = last_name
            usuario.email = email
            usuario.is_active = is_active
            usuario.save()  # primero guardamos para tener un pk antes de tocar grupos

            aplicar_rol(usuario, rol)

            if password:
                usuario.set_password(password)
                usuario.save()

            messages.success(request, "Usuario guardado correctamente.")
            return redirect("admin_panel")

        rol_actual = rol

    return render(request, "productos/admin_usuario_form.html", {
        "usuario_obj": usuario,
        "es_edicion": es_edicion,
        "roles": [(r, ROLES_GESTIONABLES[r]) for r in roles_disponibles],
        "rol_actual": rol_actual,
    })
    
@login_required(login_url='login')
@user_passes_test(puede_gestionar_usuarios, login_url='dashboard')
def admin_usuario_eliminar(request, pk):
    usuario = User.objects.filter(pk=pk).first()

    if usuario is None:
        messages.info(request, "Ese usuario ya no existe o fue eliminado.")
        return redirect("admin_panel")

    if request.method != "POST":
        return redirect("admin_panel")

    # Acá se aplica toda la jerarquía de 4 roles que armamos
    if not puede_eliminar_a(request.user, usuario):
        messages.error(request, "No tenés permiso para eliminar a este usuario.")
        return redirect("admin_panel")

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
    producto = Producto.objects.filter(pk=pk).first()
    if producto is None:
        messages.info(request, "Ese producto ya no existe o fue eliminado.")
        return redirect("dashboard")
    
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
    producto = Producto.objects.filter(pk=pk).first()
    if producto is None:
        messages.info(request, "Ese producto ya no existe o fue eliminado.")
        return redirect("dashboard")
    
    if request.method == "POST":
        try:
            cantidad_venta = int(request.POST.get("cantidad", 1))
            if cantidad_venta <= 0:
                messages.error(request, "La cantidad debe ser mayor a 0.")
                return render(request, "productos/vender.html", {"producto": producto})
        except ValueError:
            messages.error(request, "Cantidad inválida. Debe ser un número entero.")
            return render(request, "productos/vender.html", {"producto": producto})
        
        # Validar que no se venda más de lo que hay.
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
@user_passes_test(puede_eliminar_producto, login_url='dashboard')
def eliminar(request, pk):
    producto = Producto.objects.filter(pk=pk).first()
    if producto is None:
        messages.info(request, "Ese producto ya no existe o fue eliminado.")
        return redirect("dashboard")

    if request.method == "POST":
        nombre = producto.nombre
        producto.delete()
        messages.info(request, f"'{nombre}' eliminado.")
    return redirect("dashboard")

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

#    NUEVA VISTA — reemplaza la lógica del paso "escanear código"
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


@login_required(login_url='login')
def buscar_por_nombre(request):
    """
    Búsqueda combinada por NOMBRE: primero en tu catálogo propio
    (instantáneo), y si el usuario lo pide explícitamente, también
    en Open Food Facts (consulta externa, más lenta, con límite de uso).
    """
    nombre = request.GET.get("nombre", "").strip()
    incluir_externa = request.GET.get("externa") == "1"

    if not nombre or len(nombre) < 2:
        return JsonResponse({"propios": [], "externos": []})

    # 1. Buscar en tu catálogo propio — siempre, es gratis e instantáneo
    fichas_propias = CatalogoProducto.objects.filter(nombre__icontains=nombre)[:15]
    propios = [
        {
            "codigo_barra": f.codigo_barra,
            "nombre": f.nombre,
            "marca": f.marca,
            "foto": f.foto or "",
            "origen": "catalogo",
        }
        for f in fichas_propias
    ]

    externos = []
    if incluir_externa:
        # 2. Buscar en Open Food Facts — solo si el usuario lo pidió explícitamente
        #    (botón aparte), para no gastar el límite de 10 búsquedas/minuto
        #    en cada tecla que escribe.
        resultados_api = buscar_por_nombre_openfoodfacts(nombre)

        # Evitamos mostrar duplicados: si un código ya está en nuestro catálogo,
        # no lo repetimos en la sección "externos"
        codigos_propios = {f.codigo_barra for f in fichas_propias}
        externos = [
            r for r in resultados_api
            if r["codigo_barra"] not in codigos_propios
        ]

    return JsonResponse({"propios": propios, "externos": externos})


@login_required(login_url='login')
def importar_de_externa(request):
    """
    Cuando el usuario elige un resultado de Open Food Facts en el buscador,
    esta vista lo guarda en nuestro CatalogoProducto para futuras consultas.
    """
    if request.method != "POST":
        return JsonResponse({"ok": False}, status=405)

    codigo = request.POST.get("codigo_barra", "").strip()
    nombre = request.POST.get("nombre", "").strip()
    marca  = request.POST.get("marca", "").strip()
    foto_url = request.POST.get("foto_url", "").strip()

    if not codigo or not nombre:
        return JsonResponse({"ok": False, "error": "datos_incompletos"})

    ficha, creada = CatalogoProducto.objects.get_or_create(
        codigo_barra=codigo,
        defaults={
            "nombre": nombre,
            "marca": marca,
            "foto_url": foto_url,
            "origen": "api",
        },
    )

    return JsonResponse({
        "ok": True,
        "creada": creada,
        "codigo_barra": ficha.codigo_barra,
        "nombre": ficha.nombre,
    })


@login_required(login_url='login')
def pagina_buscador(request):
    """Página con el formulario de búsqueda por nombre."""
    return render(request, "productos/buscador.html")


# ───── 1. CAMBIAR CONTRASEÑA (usuario ya logueado) ─────

@login_required(login_url='login')
def cambiar_password(request):
    """
    Cualquier usuario logueado puede cambiar su propia contraseña
    desde acá, sin necesidad de ningún código por email — esto es
    distinto a "recuperar" (que es para cuando NO podés entrar).
    """
    if request.method == "POST":
        actual = request.POST.get("password_actual", "")
        nueva = request.POST.get("password_nueva", "")
        confirmar = request.POST.get("password_confirmar", "")

        if not request.user.check_password(actual):
            messages.error(request, "La contraseña actual no es correcta.")
        elif nueva != confirmar:
            messages.error(request, "Las contraseñas nuevas no coinciden.")
        elif len(nueva) < 8:
            messages.error(request, "La nueva contraseña debe tener al menos 8 caracteres.")
        else:
            request.user.set_password(nueva)
            request.user.save()
            # Esto es importante: sin esta línea, Django cerraría la
            # sesión automáticamente al cambiar la contraseña, porque
            # detecta que ya no coincide con la sesión activa.
            update_session_auth_hash(request, request.user)
            messages.success(request, "Contraseña actualizada correctamente.")
            return redirect("dashboard")

    return render(request, "productos/cambiar_password.html")


# ───── 2. SOLICITAR CÓDIGO DE RECUPERACIÓN (usuario NO logueado) ─────

def solicitar_recuperacion(request):
    """
    Paso 1 de la recuperación: el usuario ingresa su email,
    se le genera un código y se le envía por correo.
    """
    if request.method == "POST":
        email = request.POST.get("email", "").strip()

        usuario = User.objects.filter(email=email).first()

        # Por seguridad, se muestra el MISMO mensaje exista o no el
        # email en la base de datos — así nadie puede usar este
        # formulario para "adivinar" qué correos están registrados
        mensaje_generico = (
            "Si el correo está registrado, vas a recibir un código "
            "de verificación en los próximos minutos."
        )

        if usuario:
            codigo_obj = CodigoRecuperacion.generar_para(usuario)

            send_mail(
                subject="Código de recuperación — Mercatrol",
                message=(
                    f"Hola {usuario.first_name or usuario.username},\n\n"
                    f"Tu código de recuperación es: {codigo_obj.codigo}\n\n"
                    f"Este código vence en 1 minuto. Si no solicitaste "
                    f"este cambio, podés ignorar este correo."
                ),
                from_email=None,  # usa el DEFAULT_FROM_EMAIL de settings.py
                recipient_list=[usuario.email],
                fail_silently=False,
            )

            # Guardamos el ID del usuario en la sesión temporalmente,
            # para que el siguiente paso (verificar código) sepa de
            # quién se trata sin tener que pedir el email otra vez
            request.session["recuperacion_user_id"] = usuario.pk

        messages.info(request, mensaje_generico)
        return redirect("verificar_codigo")

    return render(request, "productos/solicitar_recuperacion.html")


# ───── 3. VERIFICAR CÓDIGO Y PONER NUEVA CONTRASEÑA ─────

def verificar_codigo(request):
    """
    Paso 2: el usuario escribe el código que recibió por correo,
    y si es válido, puede definir su nueva contraseña en el mismo paso.
    """
    user_id = request.session.get("recuperacion_user_id")

    if not user_id:
        messages.error(request, "Tu sesión de recuperación expiró. Solicitá el código de nuevo.")
        return redirect("solicitar_recuperacion")

    if request.method == "POST":
        codigo_ingresado = request.POST.get("codigo", "").strip()
        nueva = request.POST.get("password_nueva", "")
        confirmar = request.POST.get("password_confirmar", "")

        codigo_obj = CodigoRecuperacion.objects.filter(
            usuario_id=user_id,
            codigo=codigo_ingresado,
        ).order_by("-creado").first()

        if codigo_obj is None or not codigo_obj.valido:
            messages.error(request, "Código incorrecto o vencido. Solicitá uno nuevo.")
        elif nueva != confirmar:
            messages.error(request, "Las contraseñas no coinciden.")
        elif len(nueva) < 8:
            messages.error(request, "La contraseña debe tener al menos 8 caracteres.")
        else:
            usuario = codigo_obj.usuario
            usuario.set_password(nueva)
            usuario.save()

            codigo_obj.usado = True
            codigo_obj.save()

            # Limpiamos la sesión temporal de recuperación
            del request.session["recuperacion_user_id"]

            messages.success(request, "Contraseña actualizada. Ya podés iniciar sesión.")
            return redirect("login")

    return render(request, "productos/verificar_codigo.html")


@login_required(login_url='login')
def reportar_avaria(request):
    """
    Cualquier funcionario puede reportar una avaria.
    Escanea el código, el nombre se autocompleta desde el catálogo,
    y completa tipo de daño y cantidad.
    No pide fecha de vencimiento — eso es intencional.
    """
    if request.method == "POST":
        codigo       = request.POST.get("codigo_barra", "").strip()
        nombre       = request.POST.get("nombre", "").strip()
        cantidad_str = request.POST.get("cantidad", "1")
        tipo         = request.POST.get("tipo_danio", "").strip()

        contexto = {"tipos": Avaria.TIPOS_DANIO}

        if not codigo.isdigit():
            messages.error(request, "O código de barras só pode conter números.")
            return render(request, "productos/reportar_avaria.html", contexto)

        if not nombre:
            messages.error(request, "O nome do produto é obrigatório.")
            return render(request, "productos/reportar_avaria.html", contexto)

        try:
            cantidad = int(cantidad_str)
            if cantidad <= 0:
                raise ValueError
        except ValueError:
            messages.error(request, "A quantidade deve ser um número maior que 0.")
            return render(request, "productos/reportar_avaria.html", contexto)

        if tipo not in dict(Avaria.TIPOS_DANIO):
            messages.error(request, "Selecione um tipo de avaria válido.")
            return render(request, "productos/reportar_avaria.html", contexto)

        Avaria.objects.create(
            codigo_barra=codigo,
            nombre=nombre,
            tipo_danio=tipo,
            cantidad=cantidad,
            reportado_por=request.user,
        )

        messages.success(request, f"Avaria de '{nombre}' reportada com sucesso.")
        return redirect("listar_avarias")

    return render(request, "productos/reportar_avaria.html", {
        "tipos": Avaria.TIPOS_DANIO,
    })


@login_required(login_url='login')
def listar_avarias(request):
    """
    Lista todos los reportes de avarias.
    Cualquier funcionario puede verlos.
    Se puede filtrar por estado (pendiente/cerrado).
    """
    estado_filter = request.GET.get("estado", "pendiente")

    avarias = Avaria.objects.select_related("reportado_por", "cerrado_por")

    if estado_filter in ("pendiente", "cerrado"):
        avarias = avarias.filter(estado=estado_filter)

    return render(request, "productos/listar_avarias.html", {
        "avarias": avarias,
        "estado_filter": estado_filter,
        "total_pendientes": Avaria.objects.filter(estado="pendiente").count(),
    })


@login_required(login_url='login')
def cerrar_avaria(request, pk):
    """
    Solo Admin o superior puede cerrar un reporte de avaria.
    Cerrar significa confirmar que el producto fue dado de baja
    en el sistema externo del mercado.
    Los Trabajadores no pueden cerrar — solo reportar.
    """
    if es_trabajador(request.user):
        messages.error(request, "Você não tem permissão para fechar relatórios de avaria.")
        return redirect("listar_avarias")

    avaria = Avaria.objects.filter(pk=pk).first()
    if avaria is None:
        messages.info(request, "Esse relatório não existe mais.")
        return redirect("listar_avarias")

    if avaria.estado == "cerrado":
        messages.info(request, "Esse relatório já estava fechado.")
        return redirect("listar_avarias")

    if request.method == "POST":
        avaria.estado      = "cerrado"
        avaria.cerrado_por  = request.user
        avaria.fecha_cierre = timezone.now()
        avaria.save()
        messages.success(request, f"Avaria de '{avaria.nombre}' fechada com sucesso.")
        return redirect("listar_avarias")

    return render(request, "productos/confirmar_cierre_avaria.html", {
        "avaria": avaria
    })

    


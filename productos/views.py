from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from .models import Producto, Configuracion, ProductoDañado
import json


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
    })


@login_required(login_url='login')
def escanear(request):
    if request.method == "POST":
        codigo = request.POST.get("codigo_barra", "").strip()
        nombre = request.POST.get("nombre", "").strip()
        fecha_str = request.POST.get("fecha_vencimiento", "").strip()
        
        try:
            cantidad = int(request.POST.get("cantidad", 1))
            if cantidad <= 0:
                messages.error(request, "La cantidad debe ser mayor a 0.")
                return render(request, "productos/escanear.html")
        except ValueError:
            messages.error(request, "Cantidad inválida. Debe ser un número entero.")
            return render(request, "productos/escanear.html")

        if codigo and nombre and fecha_str:
            try:
                from datetime import date
                año, mes, dia = fecha_str.split("-")
                fecha = date(int(año), int(mes), int(dia))
                
            except (ValueError, IndexError):
                messages.error(request, "Formato de fecha inválido. Usa YYYY-MM-DD.")
                return render(request, "productos/escanear.html")

            # Si ya existe ese código con esa fecha, suma cantidad
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

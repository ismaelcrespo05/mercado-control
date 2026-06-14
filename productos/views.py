from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.utils import timezone
from .models import Producto, Configuracion
import json


def dashboard(request):
    config = Configuracion.get_config()
    hoy = timezone.now().date()

    productos = Producto.objects.all()

    vencidos = [p for p in productos if p.dias_para_vencer < 0]
    en_alerta = [p for p in productos if 0 <= p.dias_para_vencer <= config.dias_alerta]
    ok = [p for p in productos if p.dias_para_vencer > config.dias_alerta]

    return render(request, "productos/dashboard.html", {
        "config": config,
        "vencidos": vencidos,
        "en_alerta": en_alerta,
        "ok": ok,
        "hoy": hoy,
    })


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


def buscar_codigo(request):
    """AJAX: busca productos previos con ese código para autocompletar nombre."""
    codigo = request.GET.get("codigo", "")
    producto = Producto.objects.filter(codigo_barra=codigo).order_by("-fecha_registro").first()
    if producto:
        return JsonResponse({"found": True, "nombre": producto.nombre})
    return JsonResponse({"found": False})


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


def eliminar(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    if request.method == "POST":
        nombre = producto.nombre
        producto.delete()
        messages.info(request, f"'{nombre}' eliminado.")
    return redirect("dashboard")


def configuracion(request):
    config = Configuracion.get_config()
    if request.method == "POST":
        dias = int(request.POST.get("dias_alerta", 7))
        config.dias_alerta = dias
        config.save()
        messages.success(request, f"Alerta configurada a {dias} días.")
        return redirect("dashboard")
    return render(request, "productos/configuracion.html", {"config": config})

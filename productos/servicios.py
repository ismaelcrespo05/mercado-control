# ─────────────────────────────────────────────────────────────
# REEMPLAZAR el contenido completo de productos/servicios.py
# por este archivo (agrega la función de búsqueda por nombre,
# manteniendo la función de búsqueda por código que ya tenías)
# ─────────────────────────────────────────────────────────────

import requests


def buscar_en_openfoodfacts(codigo_barra):
    """
    Consulta la API pública y gratuita de Open Food Facts por CÓDIGO DE BARRA.
    Devuelve un diccionario con nombre, marca y foto si el producto existe,
    o None si no se encontró.
    """
    url = f"https://world.openfoodfacts.org/api/v2/product/{codigo_barra}.json"

    try:
        respuesta = requests.get(url, timeout=5, headers={
            "User-Agent": "VenceYa-ControlVencimientos/1.0"
        })
        datos = respuesta.json()
    except (requests.RequestException, ValueError):
        return None

    if datos.get("status") != 1:
        return None

    producto = datos.get("product", {})
    nombre = (
        producto.get("product_name_pt")
        or producto.get("product_name")
        or producto.get("product_name_es")
        or ""
    )
    if not nombre:
        return None

    foto_url = producto.get("image_front_url") or producto.get("image_url") or ""
    marca = producto.get("brands", "")

    return {
        "nombre": nombre.strip(),
        "marca": marca.strip(),
        "foto_url": foto_url,
    }


def buscar_por_nombre_openfoodfacts(nombre, limite=12):
    """
    Busca productos por NOMBRE (texto libre) en Open Food Facts.
    Devuelve una lista de hasta `limite` productos encontrados, cada uno
    con código de barra, nombre, marca y foto — para que el usuario
    elija cuál es el correcto.

    Importante: Open Food Facts limita a 10 búsquedas por minuto por IP,
    así que esta función debe llamarse solo cuando el usuario presiona
    "Buscar", nunca mientras escribe letra por letra.
    """
    if not nombre or len(nombre.strip()) < 2:
        return []

    url = "https://world.openfoodfacts.org/cgi/search.pl"
    params = {
        "search_terms": nombre.strip(),
        "search_simple": 1,
        "action": "process",
        "json": 1,
        "page_size": limite,
    }

    try:
        respuesta = requests.get(url, params=params, timeout=6, headers={
            "User-Agent": "VenceYa-ControlVencimientos/1.0"
        })
        datos = respuesta.json()
    except (requests.RequestException, ValueError):
        return []

    productos_crudos = datos.get("products", [])
    resultados = []

    for p in productos_crudos:
        codigo = p.get("code", "")
        nombre_prod = (
            p.get("product_name_pt")
            or p.get("product_name")
            or p.get("product_name_es")
            or ""
        )
        if not codigo or not nombre_prod:
            continue  # descartamos resultados incompletos

        resultados.append({
            "codigo_barra": codigo,
            "nombre": nombre_prod.strip(),
            "marca": p.get("brands", "").strip(),
            "foto_url": p.get("image_front_url") or p.get("image_url") or "",
        })

    return resultados

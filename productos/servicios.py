import requests

def buscar_en_openfoodfacts(codigo_barra):
    """
    Consulta la API pública y gratuita de Open Food Facts.
    Devuelve un diccionario con nombre, marca y foto si el producto existe,
    o None si no se encontró (código no registrado en su base de datos).

    No requiere API key. No tiene costo. No requiere autenticación.
    """
    url = f"https://world.openfoodfacts.org/api/v2/product/{codigo_barra}.json"

    try:
        respuesta = requests.get(url, timeout=5, headers={
            "User-Agent": "VenceYa-ControlVencimientos/1.0"
        })
        datos = respuesta.json()
    except (requests.RequestException, ValueError):
        # Sin internet, timeout, o respuesta inválida — no rompemos la app
        return None

    # status == 1 significa "producto encontrado"
    if datos.get("status") != 1:
        return None

    producto = datos.get("product", {})

    nombre = (
        producto.get("product_name_pt")   # nombre en portugués si existe
        or producto.get("product_name")    # nombre genérico
        or producto.get("product_name_es")
        or ""
    )

    if not nombre:
        return None  # sin nombre no sirve de mucho, lo tratamos como "no encontrado"

    foto_url = (
        producto.get("image_front_url")
        or producto.get("image_url")
        or ""
    )

    marca = producto.get("brands", "")

    return {
        "nombre": nombre.strip(),
        "marca": marca.strip(),
        "foto_url": foto_url,
    }

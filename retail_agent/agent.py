"""
agent.py
Agente de ventas y soporte para retail (demo) usando Google ADK.

Se enfoca en:
- Identificar al usuario (email / teléfono).
- Buscar productos en un catálogo de prueba.
- Armar y consultar un carrito.
- Generar un link de pago (simulado) a un formulario de YopLabs.
"""
import json
import base64

from typing import Optional, Dict, Any, List

from google.adk.agents import Agent  # type: ignore

from .data import (
    find_user_by_email_or_phone,
    create_user,
    search_products_in_catalog,
    get_product_by_id,
    get_user_by_id,
)

from .cart_store import (
    add_item_to_cart,
    get_cart_for_user,
    clear_cart_for_user,
)

from urllib.parse import quote_plus

CHECKOUT_BASE_URL = "http://localhost:8001/index.html"

# =========================
# TOOLS / FUNCIONES PARA EL AGENTE
# =========================

def identify_or_create_user(
    name: Optional[str],
    email: Optional[str],
    phone: Optional[str],
) -> Dict[str, Any]:
    """
    Identifica a un usuario por email o teléfono.
    Si no existe y se proveen name, email y phone, crea uno nuevo.

    Args:
        name: Nombre del usuario (solo obligatorio si vamos a crear uno nuevo).
        email: Email del usuario.
        phone: Teléfono del usuario (incluyendo prefijo de país, ej: +54911...).

    Returns:
        dict:
            - status: "success" o "error"
            - user: dict con datos del usuario (si success)
            - error_message: descripción (si error)
    """
    if not email and not phone:
        return {
            "status": "error",
            "error_message": "Debes proporcionar al menos email o teléfono para identificar al usuario.",
        }

    existing = find_user_by_email_or_phone(email=email, phone=phone)
    if existing:
        return {
            "status": "success",
            "user": existing,
        }

    # Si no existe, vemos si podemos crearlo
    if not (name and email and phone):
        return {
            "status": "error",
            "error_message": (
                "No encontré un usuario con esos datos. "
                "Para crear uno nuevo necesito nombre, email y teléfono."
            ),
        }

    new_user = create_user(name=name, email=email, phone=phone)

    return {
        "status": "success",
        "user": new_user,
    }


def search_products(query: str, category: Optional[str] = None) -> Dict[str, Any]:
    """
    Busca productos en el catálogo de prueba.

    Args:
        query: Texto a buscar (ej: 'leche', 'sin TACC', 'gaseosa cola').
        category: Categoría opcional (ej: 'bebidas', 'snacks', etc).

    Returns:
        dict:
            - status: "success"
            - items: lista de productos (id, name, price, is_offer)
    """
    results = search_products_in_catalog(query=query, category=category)

    simplified = [
        {
            "id": p["id"],
            "name": p["name"],
            "category": p["category"],
            "price": p["price"],
            "is_offer": p["is_offer"],
            "stock": p["stock"],
        }
        for p in results
    ]

    return {
        "status": "success",
        "items": simplified,
    }


def add_product_to_cart(
    user_id: str,
    product_id: str,
    quantity: int = 1,
) -> Dict[str, Any]:
    """
    Agrega un producto al carrito de un usuario ya identificado.

    Args:
        user_id: ID interno del usuario (campo 'id' de la base de datos).
        product_id: ID del producto (ej: 'p001').
        quantity: Cantidad a agregar (por defecto 1).

    Returns:
        dict:
            - status: "success" o "error"
            - cart: carrito actualizado (si success)
            - error_message: descripción (si error)
    """
    product = get_product_by_id(product_id)
    if not product:
        return {
            "status": "error",
            "error_message": f"No encontré un producto con id '{product_id}'.",
        }

    if quantity <= 0:
        return {
            "status": "error",
            "error_message": "La cantidad debe ser mayor a 0.",
        }

    if product["stock"] < quantity:
        return {
            "status": "error",
            "error_message": "No hay stock suficiente para esa cantidad.",
        }

    result = add_item_to_cart(user_id=user_id, product_id=product_id, quantity=quantity)
    return result


def get_cart_summary(user_id: str) -> Dict[str, Any]:
    """
    Devuelve un resumen del carrito del usuario con detalle de productos y total.

    Args:
        user_id: ID interno del usuario.

    Returns:
        dict:
            - status: "success"
            - items: lista con detalle por producto
            - total: total en moneda
    """
    cart_info = get_cart_for_user(user_id)
    items = cart_info.get("cart", [])

    detailed_items: List[Dict[str, Any]] = []
    total = 0.0

    for item in items:
        product = get_product_by_id(item["product_id"])
        if not product:
            # Producto borrado del catálogo, lo ignoramos
            continue

        line_total = product["price"] * item["quantity"]
        total += line_total

        detailed_items.append(
            {
                "product_id": product["id"],
                "name": product["name"],
                "quantity": item["quantity"],
                "unit_price": product["price"],
                "line_total": line_total,
            }
        )

    return {
        "status": "success",
        "items": detailed_items,
        "total": total,
    }

def checkout_cart(user_id: str, email: str) -> Dict[str, Any]:
    """
    Simula el checkout del carrito y genera una URL de pago
    que apunta a una página de checkout (web) donde se muestran
    los datos del usuario y el total.

    Args:
        user_id: ID interno del usuario.
        email: Email del usuario (para precargarlo en el form).

    Returns:
        dict:
            - status: "success" o "error"
            - total: total del carrito (si success)
            - payment_url: URL de checkout (si success)
            - error_message: descripción (si error)
    """
    summary = get_cart_summary(user_id)
    if summary["status"] != "success":
        return summary

    total = summary.get("total", 0.0)
    items = summary.get("items", [])

    if not items:
        return {
            "status": "error",
            "error_message": "El carrito está vacío, no hay nada para pagar.",
        }

    # Obtenemos el nombre del usuario para mostrarlo en el checkout
    user = get_user_by_id(user_id)

    # Si no se encuentra por id, probamos buscarlo por email
    if not user:
        user = find_user_by_email_or_phone(email=email, phone=None)

    user_name = user["name"] if user else "Cliente"
    user_id_resolved = user["id"] if user else "unknown"

    items_payload = base64.urlsafe_b64encode(
    json.dumps(items).encode("utf-8")
    ).decode("utf-8")
    
    # Armamos la URL del checkout con query params
    payment_url = (
    f"{CHECKOUT_BASE_URL}"
        f"?user_id={quote_plus(user_id_resolved)}"
        f"&name={quote_plus(user_name)}"
        f"&email={quote_plus(email)}"
        f"&amount={total:.2f}"
        f"&items={items_payload}"
    )

    # Para demo, limpiamos el carrito luego del checkout
    clear_cart_for_user(user_id)

    return {
        "status": "success",
        "total": total,
        "payment_url": payment_url,
    }


# =========================
# DEFINICIÓN DEL AGENTE ADK
# =========================

root_agent = Agent(
    name="retail_assistant",
    model="gemini-2.0-flash",  # Modelo por defecto según quickstart de ADK
    description=(
        "Asistente de supermercado para ventas y soporte en retail. "
        "Ayuda al usuario a encontrar productos, ver precios, ofertas "
        "y armar su carrito de compras."
    ),
    instruction=(
        "Sos un asistente de supermercado amable, directo y conversacional. "
        "El usuario está chateando desde WhatsApp, así que respondé breve, claro y en tono rioplatense.\n\n"

        "TU OBJETIVO PRINCIPAL ES:\n"
        "- Identificar al usuario (nombre, email y teléfono).\n"
        "- Buscar productos por nombre, descripción o categoría.\n"
        "- Sugerir ofertas si aplica.\n"
        "- Armar, modificar y revisar el carrito.\n"
        "- Finalizar la compra generando un link de pago.\n\n"

        "REGLAS ESTRICTAS PARA USAR LAS TOOLS:\n"
        "- identify_or_create_user: usá SIEMPRE esta tool cuando necesites saber quién es el usuario.\n"
        "- search_products: usá esta tool cuando el usuario pida buscar, ver, mostrar o consultar productos.\n"
        "- add_product_to_cart: usala SOLO cuando el usuario pida explícitamente agregar, sumar o cargar un producto al carrito.\n"
        "- get_cart_summary: usala cuando el usuario pregunte por el resumen del carrito.\n"
        "- checkout_cart: usala cuando el usuario diga que quiere pagar o finalizar.\n\n"

        "IDENTIFICACIÓN DEL USUARIO:\n"
        "Cuando el usuario diga algo como 'mi nombre es X, mi mail es Y, mi teléfono es Z', "
        "llamá SIEMPRE a identify_or_create_user con parámetros explícitos:\n"
        "- name\n"
        "- email\n"
        "- phone\n"
        "Incluso si lo menciona en una sola frase o con palabras sueltas, extraé los valores completos.\n\n"

        "No llames identify_or_create_user sin los tres parámetros completos.\n"
        "No inventes datos. No uses cadenas vacías ni null. Extraé todo del mensaje del usuario.\n\n"

        "CUANDO identify_or_create_user devuelva un usuario:\n"
        "- Si segment = 'nuevo', decí algo como: 'Te acabo de registrar con esos datos'.\n"
        "- Si segment es otro valor, decí algo como: 'Ya te tenía registrado acá, Pablo' o similar.\n\n"

        "BÚSQUEDA INTELIGENTE DE PRODUCTOS:\n"
        "- Si search_products no encuentra resultados, NO digas 'qué raro', ni describas tu proceso técnico.\n"
        "- En lugar de eso, decí algo simple como: 'No encontré exactamente eso, pero te muestro lo más parecido'.\n"
        "- Volvé a llamar a search_products con un query más general (por ejemplo: si pidió 'pan lactal', probá 'pan').\n"
        "- Siempre respondé con lo que realmente devuelva la tool, sin inventar productos.\n\n"

        "COMPORTAMIENTO EN EL CARRITO:\n"
        "- Si el usuario dice 'agregame X', extraé qué producto es y cuántas unidades, y usá add_product_to_cart.\n"
        "- Si no está identificado todavía, pedile identificación ANTES de agregar.\n\n"

        "CHECKOUT:\n"
        "- Cuando el usuario diga 'quiero pagar', 'finalizar', 'comprar', 'checkout', llamá checkout_cart.\n"
        "- No inventes el link. Usá el payment_url EXACTO que devuelve la tool.\n\n"

        "TONO Y ESTILO:\n"
        "- WhatsApp breve, humano y natural.\n"
        "- No uses tecnicismos. No describas procesos internos.\n"
        "- No expliques cómo funcionan las tools.\n"
        "- No digas 'estoy llamando a una tool' ni 'estoy ejecutando una acción'.\n"
        "- Mantené un tono amable, pero profesional y simple.\n\n"

        "MUY IMPORTANTE:\n"
        "- No inventes parámetros para herramientas.\n"
        "- No fabriques datos (productos, precios, nombres, IDs).\n"
        "- No asumas nada que no se dijo explícitamente.\n"
        "- Extraé SIEMPRE los datos del mensaje del usuario.\n"
    ),
    tools=[
        identify_or_create_user,
        search_products,
        add_product_to_cart,
        get_cart_summary,
        checkout_cart,
    ],
)

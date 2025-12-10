# agent_tools_backoffice.py
"""
Tools que usa el agente de retail para hablar con el backoffice
(FastAPI + retail.db).

Incluye:
- identify_or_create_user
- search_products
- add_product_to_cart
- get_cart_summary
- checkout_cart
"""

import os
from typing import List, Dict, Any, Optional

import requests

# Base URL del backoffice (FastAPI)
# En local: http://localhost:8000
BACKOFFICE_BASE_URL = os.getenv("BACKOFFICE_BASE_URL", "http://localhost:8000")

# (Opcional) URL base del checkout web, para fallback si el back no envía link
CHECKOUT_BASE_URL = os.getenv(
    "CHECKOUT_BASE_URL", "http://localhost:8001/index.html"
)


def _api_get(path: str, params: Optional[Dict[str, Any]] = None) -> Any:
    """
    Helper para hacer GET al backoffice.
    Devuelve None si el status es 404, lanza excepción en otros errores.
    """
    url = f"{BACKOFFICE_BASE_URL}{path}"
    resp = requests.get(url, params=params, timeout=5)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def _api_post(path: str, json_data: Dict[str, Any]) -> Any:
    """
    Helper para hacer POST al backoffice.
    """
    url = f"{BACKOFFICE_BASE_URL}{path}"
    resp = requests.post(url, json=json_data, timeout=5)
    resp.raise_for_status()
    return resp.json()


# =====================================================
# TOOL 1: identify_or_create_user
# =====================================================

def identify_or_create_user(
    name: Optional[str],
    email: Optional[str],
    phone: Optional[str],
) -> Dict[str, Any]:
    """
    Identifica o crea un usuario usando el backoffice, aceptando cualquiera
    de estos datos: nombre o email o teléfono.

    Flujo:
    1) Busca en /users/search con lo que tenga (email/phone/name).
    2) Si encuentra 1 usuario -> status 'found'.
    3) Si encuentra varios -> status 'ambiguous' con candidatos.
    4) Si no encuentra ninguno:
       - Si hay email -> crea usuario nuevo (segment='nuevo'), status 'created'.
       - Si NO hay email -> status 'error' pidiendo el mail.
    """

    # Si no tiene NADA, no podemos hacer magia
    if not any([name, email, phone]):
        return {
            "status": "error",
            "error_message": (
                "Necesito al menos uno de estos datos para encontrarte: "
                "nombre, email o teléfono."
            ),
        }

    # 1) Buscar con lo que tengamos
    try:
        params: Dict[str, Any] = {}

        if email is not None and email != "":
            params["email"] = email

        if phone is not None and phone != "":
            params["phone"] = phone

        if name is not None and name != "":
            params["name"] = name

        # Limpieza final
        params = {k: v for k, v in params.items() if v not in (None, "", "null")}

        users = _api_get("/users/search", params=params) or []
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"No pude consultar la base de clientes. Detalle: {e}",
        }

    # 2) Si encontró usuarios
    if len(users) == 1:
        u = users[0]
        return {
            "status": "found",
            "user": {
                "id": u["id"],
                "name": u["name"],
                "email": u["email"],
                "phone": u.get("phone"),
                "segment": u.get("segment", "recurrente"),
            },
        }

    if len(users) > 1:
        # Devolvemos candidatos para que el LLM los use en el mensaje
        candidates = []
        for u in users:
            candidates.append(
                {
                    "id": u["id"],
                    "name": u["name"],
                    "email": u["email"],
                    "phone": u.get("phone"),
                }
            )
        return {
            "status": "ambiguous",
            "candidates": candidates,
            "error_message": (
                "Encontré más de un posible usuario con esos datos. "
                "Pedile al usuario que confirme cuál es."
            ),
        }

    # 3) No encontró ninguno -> crear
    if not email:
        # No podemos crear usuario sin email porque el schema lo exige
        return {
            "status": "error",
            "error_message": (
                "No encontré un usuario con esos datos y para crearte necesito "
                "también un email. ¿Me lo pasás?"
            ),
        }

    safe_name = name or "Cliente"
    safe_phone = phone or ""

    try:
        new_user = _api_post(
            "/users",
            {
                "name": safe_name,
                "email": email,
                "phone": safe_phone,
                "segment": "nuevo",
            },
        )
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"No pude crearte como nuevo cliente. Detalle: {e}",
        }

    return {
        "status": "created",
        "user": {
            "id": new_user["id"],
            "name": new_user["name"],
            "email": new_user["email"],
            "phone": new_user.get("phone"),
            "segment": new_user.get("segment", "nuevo"),
        },
    }


# =====================================================
# TOOL 2: search_products
# =====================================================

def search_products(
    query: str,
    category: Optional[str] = None,
    only_offers: bool = False,
) -> Dict[str, Any]:
    """
    Busca productos en el catálogo real del backoffice.

    Implementación:
    - GET /products
    - Filtra en memoria:
      - texto (name, description, category, sku)
      - categoría (opcional)
      - solo ofertas (opcional).

    Devuelve:
      {
        "status": "success",
        "items": [ {id, sku, name, category, price, is_offer, stock}, ... ]
      }
    """
    try:
        products = _api_get("/products") or []
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"No pude consultar el catálogo del backoffice. Detalle: {e}",
        }

    q = (query or "").strip().lower()

    def matches(p: Dict[str, Any]) -> bool:
        # filtro textual
        if q:
            text = " ".join(
                [
                    str(p.get("name", "")),
                    str(p.get("description", "")),
                    str(p.get("category", "")),
                    str(p.get("sku", "")),
                ]
            ).lower()
            if q not in text:
                return False

        # filtro por categoría
        if category:
            cat = str(p.get("category") or "").lower()
            if category.lower() not in cat:
                return False

        # filtro por ofertas
        if only_offers:
            if not bool(p.get("is_offer")):
                return False

        return True

    filtered = [p for p in products if matches(p)]
    simplified = [
        {
            "id": p["id"],
            "sku": p["sku"],
            "name": p["name"],
            "category": p.get("category"),
            "price": p["price"],
            "is_offer": bool(p.get("is_offer")),
            "stock": p.get("stock", 0),
        }
        for p in filtered[:25]
    ]

    return {
        "status": "success",
        "items": simplified,
    }


# =====================================================
# TOOL 3: add_product_to_cart
# =====================================================

def add_product_to_cart(
    user_id: int,
    product_id: int,
    quantity: int = 1,
) -> Dict[str, Any]:
    """
    Agrega un producto al carrito del usuario en el backoffice.

    Requiere endpoint en FastAPI:
    POST /carts/add_item
    body: { "user_id": int, "product_id": int, "quantity": int }
    resp: { "cart_id": int, "user_id": int,
            "items": [...], "total": float }
    """
    if quantity <= 0:
        return {
            "status": "error",
            "error_message": "La cantidad debe ser mayor a 0.",
        }

    try:
        cart = _api_post(
            "/carts/add_item",
            {
                "user_id": user_id,
                "product_id": product_id,
                "quantity": quantity,
            },
        )
    except Exception as e:
        return {
            "status": "error",
            "error_message": (
                "No pude agregar el producto al carrito en el backoffice. "
                f"Detalle: {e}"
            ),
        }

    return {
        "status": "success",
        "cart": cart,
    }


# =====================================================
# TOOL 4: get_cart_summary
# =====================================================

def get_cart_summary(user_id: int) -> Dict[str, Any]:
    """
    Devuelve el resumen del carrito del usuario.

    Requiere endpoint:
    GET /carts/summary?user_id=...
    resp:
      {
        "cart_id": int,
        "user_id": int,
        "items": [
          {product_id, name, quantity, unit_price, line_total}, ...
        ],
        "total": float
      }
    """
    try:
        summary = _api_get("/carts/summary", params={"user_id": user_id})
    except Exception as e:
        return {
            "status": "error",
            "error_message": (
                "No pude obtener el carrito desde el backoffice. "
                f"Detalle: {e}"
            ),
        }

    if summary is None:
        return {
            "status": "success",
            "items": [],
            "total": 0.0,
        }

    return {
        "status": "success",
        "items": summary.get("items", []),
        "total": summary.get("total", 0.0),
        "cart_id": summary.get("cart_id"),
    }


# =====================================================
# TOOL 5: checkout_cart
# =====================================================

def checkout_cart(user_id: int, email: str) -> Dict[str, Any]:
    """
    Hace checkout del carrito en el backoffice y genera un link de pago.

    Requiere endpoint:
    POST /orders/checkout
    body: { "user_id": int, "email": str }
    resp:
      {
        "order_id": int,
        "total": float,
        "payment_url": str
      }
    """
    try:
        result = _api_post(
            "/orders/checkout",
            {
                "user_id": user_id,
                "email": email,
            },
        )
    except Exception as e:
        return {
            "status": "error",
            "error_message": (
                "No pude finalizar la compra en el backoffice. "
                f"Detalle: {e}"
            ),
        }

    return {
        "status": "success",
        "total": result.get("total", 0.0),
        "payment_url": result.get("payment_url", CHECKOUT_BASE_URL),
        "order_id": result.get("order_id"),
    }

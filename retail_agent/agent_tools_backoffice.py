"""
Tools que usa el agente de retail para hablar con el backoffice
(FastAPI + retail.db).

Incluye:
- search_users (NUEVA - busca usuarios y devuelve candidatos)
- create_user (NUEVA - crea usuario directamente)
- search_products
- add_product_to_cart
- get_cart_summary
- checkout_cart
"""

import os
from typing import List, Dict, Any, Optional

import requests

# Base URL del backoffice (FastAPI)
BACKOFFICE_BASE_URL = os.getenv("BACKOFFICE_BASE_URL", "http://localhost:8000")
CHECKOUT_BASE_URL = os.getenv("CHECKOUT_BASE_URL", "http://localhost:8001/index.html")


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
# TOOL 1: search_users (NUEVA - simplificada)
# =====================================================

def search_users(
    name: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Busca usuarios en la base de datos usando cualquier combinación de:
    - name (búsqueda parcial)
    - email (búsqueda exacta, vía /users/search?email=...)
    - phone (búsqueda exacta)

    Devuelve:
    - status: "found" | "multiple" | "not_found" | "error"
    - users: lista de candidatos
    """

    if not any([name, email, phone]):
        return {
            "status": "error",
            "error_message": "Necesito al menos un dato para buscar (nombre, email o teléfono)",
            "users": [],
        }

    try:
        params: Dict[str, Any] = {}

        # Si viene solo email, igual usamos /users/search, pero la lógica
        # de interpretación es la misma: lista de usuarios.
        if email:
            params["email"] = email
        if phone:
            params["phone"] = phone
        if name:
            params["name"] = name

        params = {k: v for k, v in params.items() if v and v != "null"}

        users = _api_get("/users/search", params=params) or []

        candidates = [
            {
                "id": u["id"],
                "name": u["name"],
                "email": u["email"],
                "phone": u.get("phone", ""),
                "segment": u.get("segment", "recurrente"),
            }
            for u in users
        ]

        if len(candidates) == 0:
            return {
                "status": "not_found",
                "message": "No encontré usuarios con esos datos. Podés crear uno nuevo.",
                "users": [],
            }

        if len(candidates) == 1:
            return {
                "status": "found",
                "message": f"Encontré 1 usuario: {candidates[0]['name']} ({candidates[0]['email']})",
                "users": candidates,
            }

        return {
            "status": "multiple",
            "message": f"Encontré {len(candidates)} usuarios. Preguntale cuál corresponde.",
            "users": candidates,
        }

    except Exception as e:
        return {
            "status": "error",
            "error_message": f"Error al buscar usuarios: {e}",
            "users": [],
        }


# =====================================================
# TOOL 2: create_user (NUEVA - simplificada)
# =====================================================

def create_user(
    name: str,
    email: str,
    phone: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Crea un nuevo usuario en la base de datos.

    Comportamiento robusto / tolerante al modelo:
    - Primero busca por email con /users/search.
    - Si ya existe, devuelve status="exists" con ese usuario.
    - Si no existe, lo crea y devuelve status="created".
    """

    if not name or not email:
        return {
            "status": "error",
            "error_message": "Para crear un usuario necesito nombre y email",
        }

    try:
        # 1) Ver si ya existe el email usando /users/search
        try:
            existing_list = _api_get("/users/search", params={"email": email}) or []
        except Exception:
            existing_list = []

        if existing_list:
            # Tomamos el primero, debería ser único por email
            existing = existing_list[0]
            return {
                "status": "exists",
                "message": f"El email {email} ya estaba registrado. Uso ese usuario.",
                "user": {
                    "id": existing["id"],
                    "name": existing["name"],
                    "email": existing["email"],
                    "phone": existing.get("phone"),
                    "segment": existing.get("segment", "recurrente"),
                },
            }

        # 2) Crear nuevo usuario
        new_user = _api_post(
            "/users",
            {
                "name": name,
                "email": email,
                "phone": phone or "",
                "segment": "nuevo",
            },
        )

        return {
            "status": "created",
            "message": f"Usuario creado exitosamente: {new_user['name']} ({new_user['email']})",
            "user": {
                "id": new_user["id"],
                "name": new_user["name"],
                "email": new_user["email"],
                "phone": new_user.get("phone"),
                "segment": new_user.get("segment", "nuevo"),
            },
        }

    except requests.exceptions.HTTPError as e:
        return {
            "status": "error",
            "error_message": f"Error al crear usuario: {e}",
        }
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"Error inesperado al crear usuario: {e}",
        }




# =====================================================
# TOOL 3: search_products (sin cambios)
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
# TOOL 4: add_product_to_cart (mejorado con validación)
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

    # Validar que el usuario existe
    try:
        user = _api_get(f"/users/{user_id}")
        if not user:
            return {
                "status": "error",
                "error_message": f"El usuario con ID {user_id} no existe. Necesitás buscar o crear el usuario primero."
            }
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"No pude verificar el usuario: {e}"
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
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            return {
                "status": "error",
                "error_message": "El producto no existe o no está disponible."
            }
        return {
            "status": "error",
            "error_message": f"No pude agregar el producto al carrito: {e}"
        }
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"Error inesperado: {e}"
        }

    return {
        "status": "success",
        "message": f"Agregado al carrito: {quantity}x producto ID {product_id}",
        "cart": cart,
    }


# =====================================================
# TOOL 5: get_cart_summary (sin cambios)
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
# TOOL 6: checkout_cart (sin cambios)
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
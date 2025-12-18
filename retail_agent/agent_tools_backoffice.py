"""
Tools que usa el agente de retail para hablar con el backoffice
(FastAPI + retail.db).

Incluye:
- search_users (NUEVA - busca usuarios y devuelve candidatos)
- create_user (NUEVA - crea usuario directamente)
- search_products
- add_product_to_cart
- get_cart_summary
- clear_cart
- checkout_cart
- get_last_order_status
- get_checkout_link_for_last_order
"""

import os
from typing import List, Dict, Any, Optional

import requests

# =====================================================
# ENV / CONFIG
# =====================================================

# Base URL del backoffice (FastAPI)
# - En Cloud Run usamos la URL pública con optimizaciones
ENV_MODE = (os.getenv("ENV", "") or "").lower()

BACKOFFICE_BASE_URL = os.getenv("BACKOFFICE_BASE_URL")
if not BACKOFFICE_BASE_URL:
    if ENV_MODE in ("dev", "local", ""):
        BACKOFFICE_BASE_URL = "http://127.0.0.1:8080"
    else:
        raise RuntimeError("BACKOFFICE_BASE_URL faltante")

# normalizar (evita //)
BACKOFFICE_BASE_URL = BACKOFFICE_BASE_URL.rstrip("/")

CHECKOUT_BASE_URL = os.getenv("CHECKOUT_BASE_URL")
if not CHECKOUT_BASE_URL:
    if ENV_MODE in ("dev", "local", ""):
        CHECKOUT_BASE_URL = "http://localhost:8001/index.html"
    else:
        raise RuntimeError("CHECKOUT_BASE_URL faltante")

BACKOFFICE_API_KEY = os.getenv("BACKOFFICE_API_KEY")
if not BACKOFFICE_API_KEY:
    raise RuntimeError("BACKOFFICE_API_KEY faltante")

_session = requests.Session()
# Optimizaciones para reducir latencia
_session.headers.update({'Connection': 'keep-alive'})
# Pool de conexiones para reusar sockets
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

retry_strategy = Retry(
    total=2,
    backoff_factor=0.1,
    status_forcelist=[500, 502, 503, 504],
)
adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=20)
_session.mount("http://", adapter)
_session.mount("https://", adapter)

def _auth_headers() -> Dict[str, str]:
    # EXACTO como lo espera FastAPI (Header -> x-api-key)
    return {"x-api-key": BACKOFFICE_API_KEY}

# =====================================================
# HTTP HELPERS (UNA SOLA DEFINICIÓN, SIN DUPLICADOS)
# =====================================================

def _api_get(path: str, params: Optional[Dict[str, Any]] = None) -> Any:
    """
    GET al backoffice.
    - Si devuelve 404 -> retorna None (para flujos tipo "no existe").
    - Si devuelve 2xx -> retorna JSON.
    - Si devuelve otro error -> levanta excepción (las tools lo capturan y normalizan).
    """
    url = f"{BACKOFFICE_BASE_URL}{path}"
    # Timeout más agresivo: (connect_timeout, read_timeout)
    resp = _session.get(url, params=params, headers=_auth_headers(), timeout=(2, 8))
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()

def _api_post(path: str, json_data: Dict[str, Any]) -> Any:
    """
    POST al backoffice.
    - Si devuelve 2xx -> retorna JSON.
    - Si devuelve error -> levanta excepción (las tools lo capturan y normalizan).
    """
    url = f"{BACKOFFICE_BASE_URL}{path}"
    # Timeout más agresivo
    resp = _session.post(url, json=json_data, headers=_auth_headers(), timeout=(2, 8))
    resp.raise_for_status()
    return resp.json()

# =====================================================
# TOOL 1: search_users (mejorada + normalización)
# =====================================================

def search_users(
    name: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Busca usuarios en la base de datos usando cualquier combinación de:
    - name (búsqueda parcial)
    - email (búsqueda exacta)
    - phone (búsqueda exacta)

    Devuelve:
    - status: "found" | "multiple" | "not_found" | "error"
    - users: lista de candidatos
    """

    # -------------------------
    # Normalización de inputs
    # -------------------------
    if email:
        email = str(email).strip().lower()

    if phone:
        # puede venir como "+549...", "whatsapp:+549...", etc.
        phone = str(phone).strip()
        phone = phone.replace("whatsapp:", "")
        phone = "".join([c for c in phone if c.isdigit()])

    if name:
        name = " ".join(str(name).strip().split())  # trim + colapsar espacios

    # Anti "null" / vacíos
    def _is_valid(v: Optional[str]) -> bool:
        if v is None:
            return False
        s = str(v).strip()
        return bool(s) and s.lower() not in ("null", "none", "undefined")

    if not any([_is_valid(name), _is_valid(email), _is_valid(phone)]):
        return {
            "status": "error",
            "error_message": "Necesito al menos un dato válido para buscar (nombre, email o teléfono).",
            "users": [],
        }

    try:
        params: Dict[str, Any] = {}
        if _is_valid(email):
            params["email"] = email
        if _is_valid(phone):
            params["phone"] = phone
        if _is_valid(name):
            params["name"] = name

        users = _api_get("/users/search", params=params) or []

        candidates = [
            {
                "id": u["id"],
                "name": u.get("name", ""),
                "email": u.get("email", ""),
                "phone": u.get("phone", "") or "",
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
            "message": f"Encontré {len(candidates)} usuarios. Decime cuál corresponde.",
            "users": candidates,
        }

    except Exception as e:
        return {
            "status": "error",
            "error_message": f"Error al buscar usuarios: {e}",
            "users": [],
        }

# =====================================================
# TOOL 2: create_user (mejorada + normalización)
# =====================================================

def create_user(
    name: str,
    email: str,
    phone: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Crea un nuevo usuario en la base de datos.
    
    OPTIMIZADO: Intenta crear directamente. Si falla por duplicado, es porque ya existe.
    """
    print(f"🆕 create_user called: name={name}, email={email}, phone={phone}")

    # Normalización
    name = " ".join((name or "").strip().split())
    email = (email or "").strip().lower()

    if phone:
        phone = str(phone).strip().replace("whatsapp:", "")
        phone = "".join([c for c in phone if c.isdigit()])
    else:
        phone = ""

    if not name or not email:
        return {
            "status": "error",
            "error_message": "Para crear un usuario necesito nombre y email.",
        }

    try:
        # Intento crear directamente (optimista)
        new_user = _api_post(
            "/users",
            {
                "name": name,
                "email": email,
                "phone": phone,
                "segment": "nuevo",
            },
        )

        print(f"✅ Usuario creado: id={new_user['id']}")
        
        return {
            "status": "created",
            "message": f"Usuario creado exitosamente: {new_user.get('name','')} ({new_user.get('email','')})",
            "user": {
                "id": new_user["id"],
                "name": new_user.get("name", ""),
                "email": new_user.get("email", ""),
                "phone": new_user.get("phone", ""),
                "segment": new_user.get("segment", "nuevo"),
            },
        }

    except requests.exceptions.HTTPError as e:
        # Si es 400, probablemente email duplicado
        print(f"⚠️  HTTPError al crear usuario: {e.response.status_code if e.response else 'unknown'}")
        if e.response is not None and e.response.status_code == 400:
            # Buscar el usuario existente por email
            try:
                existing = _api_get("/users/search", params={"email": email}) or []
                if existing:
                    user = existing[0]
                    print(f"⚠️  Usuario ya existía: id={user['id']}")
                    return {
                        "status": "exists",
                        "message": f"El email {email} ya estaba registrado. Uso ese usuario.",
                        "user": {
                            "id": user["id"],
                            "name": user.get("name", ""),
                            "email": user.get("email", ""),
                            "phone": user.get("phone", ""),
                            "segment": user.get("segment", "recurrente"),
                        },
                    }
            except Exception:
                pass
        
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

    # -------------------------
    # Validación básica
    # -------------------------
    if quantity <= 0:
        return {
            "status": "error",
            "error_message": "La cantidad debe ser mayor a 0.",
        }

    # -------------------------
    # Validar que el usuario existe
    # -------------------------
    try:
        user = _api_get(f"/users/{user_id}")
        if not user:
            return {
                "status": "error",
                "error_message": (
                    f"El usuario con ID {user_id} no existe. "
                    "Necesitás buscar o crear el usuario primero."
                ),
            }
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"No pude verificar el usuario: {e}",
        }

    # -------------------------
    # Validar stock disponible
    # -------------------------
    try:
        products = _api_get("/products") or []
        p = next(
            (x for x in products if int(x.get("id")) == int(product_id)),
            None
        )

        if not p:
            return {
                "status": "error",
                "error_message": "El producto no existe o no está disponible.",
            }

        product_name = p.get("name", "este producto")
        stock = int(p.get("stock", 0) or 0)

        if stock <= 0:
            return {
                "status": "error",
                "error_message": f"No hay stock disponible para '{product_name}'.",
                "available_stock": 0,
                "product_name": product_name,
            }

        if quantity > stock:
            return {
                "status": "error",
                "error_message": (
                    f"No hay stock suficiente para '{product_name}'. "
                    f"Stock disponible: {stock}. Pedime una cantidad menor."
                ),
                "available_stock": stock,
                "product_name": product_name,
            }

    except Exception as e:
        # Fail-closed: preferimos NO agregar si no pudimos validar stock
        return {
            "status": "error",
            "error_message": (
                "No pude verificar el stock en este momento. "
                f"Detalle: {e}"
            ),
        }

    # -------------------------
    # Agregar al carrito
    # -------------------------
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
        if getattr(e.response, "status_code", None) == 404:
            return {
                "status": "error",
                "error_message": "El producto no existe o no está disponible.",
            }
        return {
            "status": "error",
            "error_message": f"No pude agregar el producto al carrito: {e}",
        }

    except Exception as e:
        return {
            "status": "error",
            "error_message": f"Error inesperado al agregar al carrito: {e}",
        }

    # -------------------------
    # Success
    # -------------------------
    return {
        "status": "success",
        "message": f"Agregado al carrito: {quantity}x {product_name}",
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

def clear_cart(user_id: int) -> Dict[str, Any]:
    """
    Reinicia (vacía) el carrito abierto del usuario.
    Requiere endpoint:
    POST /carts/clear
    body: {"user_id": int}
    """
    try:
        result = _api_post("/carts/clear", {"user_id": user_id})
        return result if isinstance(result, dict) else {
            "status": "error",
            "error_message": "Respuesta inválida al reiniciar el carrito."
        }
    except requests.exceptions.HTTPError as e:
        return {
            "status": "error",
            "error_message": f"No pude reiniciar el carrito: {e}",
        }
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"Error inesperado al reiniciar el carrito: {e}",
        }

# =====================================================
# TOOL 6: checkout_cart (sin cambios)
# =====================================================

def checkout_cart(user_id: int, email: str) -> Dict[str, Any]:
    """
    Hace checkout del carrito en el backoffice y genera un link de pago corto.

    Flujo:
    - Llama a POST /orders/checkout → crea la orden en la base
      (si existe un carrito abierto para ese usuario).
    - Construye una URL corta: {BACKOFFICE_BASE_URL}/checkout/{order_id}
    """

    try:
        result = _api_post(
            "/orders/checkout",
            {
                "user_id": user_id,
                "email": email,
            },
        )
    except requests.exceptions.HTTPError as e:
        # Errores esperables desde el backoffice
        if e.response is not None and e.response.status_code == 400:
            # Ej: "El usuario no tiene un carrito abierto para checkout."
            return {
                "status": "error",
                "error_message": "No encontré un carrito abierto para este usuario. Primero hay que armar el carrito.",
            }
        return {
            "status": "error",
            "error_message": f"No pude finalizar la compra en el backoffice: {e}",
        }
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"Error inesperado al finalizar la compra: {e}",
        }

    order_id = result.get("order_id")
    short_url = None
    if order_id is not None:
        # Usa la API del backoffice para redirigir a index.html
        short_url = f"{BACKOFFICE_BASE_URL}/checkout/{order_id}"

    return {
        "status": "success",
        "total": result.get("total", 0.0),
        # Siempre priorizamos el link corto; si por algún motivo no se arma,
        # usamos el payment_url que devuelva el backoffice como fallback.
        "payment_url": short_url or result.get("payment_url", CHECKOUT_BASE_URL),
        "order_id": order_id,
    }

def get_last_order_status(user_id: int, limit: int = 1) -> Dict[str, Any]:
    """
    Devuelve el último pedido del usuario.

    Respuesta normalizada para el agente:
    {
        "status": "found" | "not_found" | "error",
        "message": "...",
        "orders": [ { ...pedido... } ]
    }
    """
    try:
        result = _api_get(
            "/orders/last",
            params={"user_id": user_id}
        )

        if not result:
            return {
                "status": "not_found",
                "message": "No encontré pedidos para este usuario.",
                "orders": [],
            }

        if result.get("status") != "found" or "order" not in result:
            return {
                "status": "not_found",
                "message": "No encontré pedidos para este usuario.",
                "orders": [],
            }

        order = result["order"]

        return {
            "status": "found",
            "message": "Pedido encontrado.",
            "orders": [order],   # lo devolvemos siempre como lista
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Error consultando pedidos: {e}",
            "orders": [],
        }

def get_checkout_link_for_last_order(user_id: int) -> Dict[str, Any]:
    """
    Devuelve el payment_url corto para el último pedido del usuario.
    Internamente llama a /orders/by_user y construye /checkout/{order_id}.
    """
    try:
        orders = _api_get("/orders/by_user", params={"user_id": user_id, "limit": 1})

        if not orders:
            return {
                "status": "not_found",
                "message": "Este usuario no tiene pedidos previos."
            }

        order = orders[0]
        order_id = order["id"]

        return {
            "status": "success",
            "order_id": order_id,
            "payment_url": f"{BACKOFFICE_BASE_URL}/checkout/{order_id}"
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Error al obtener el link de pago: {e}"
        }

# =====================================================
# TOOL 10: update_user_profile (LEAD CAPTURE)
# =====================================================

def update_user_profile(
    user_id: int,
    profession: Optional[str] = None,
    company: Optional[str] = None,
    industry: Optional[str] = None,
    comments: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Actualiza el perfil del usuario con información de negocio (lead capture).
    
    Args:
        user_id: ID del usuario
        profession: Profesión/rol (ej: "Gerente de Marketing")
        company: Empresa donde trabaja
        industry: Industria/sector (ej: "Retail", "E-commerce")
        comments: Comentarios adicionales
    
    Returns:
        {"status": "success" | "error", "message": "..."}
    """
    print(f"📊 update_user_profile called: user_id={user_id}")
    
    # Validar que hay al menos un campo para actualizar
    if not any([profession, company, industry, comments]):
        return {
            "status": "error",
            "message": "Necesito al menos un dato para actualizar."
        }
    
    try:
        # Construir el payload solo con campos que no son None
        data = {"user_id": user_id}
        if profession:
            data["profession"] = profession.strip()
        if company:
            data["company"] = company.strip()
        if industry:
            data["industry"] = industry.strip()
        if comments:
            data["comments"] = comments.strip()
        
        # Llamar al endpoint del backoffice
        result = _api_post("/users/update_profile", data)
        
        print(f"✅ Perfil actualizado: user_id={user_id}")
        
        return {
            "status": "success",
            "message": "Perfil actualizado exitosamente."
        }
    
    except requests.exceptions.HTTPError as e:
        return {
            "status": "error",
            "message": f"Error al actualizar perfil: {e}"
        }
    
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error inesperado: {e}"
        }

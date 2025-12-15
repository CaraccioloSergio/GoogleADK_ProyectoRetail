from pathlib import Path
from typing import List, Optional, Dict, Any 

import os
from dotenv import load_dotenv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
RETAIL_AGENT_DIR = BASE_DIR / "retail_agent"
ENV_PATH = RETAIL_AGENT_DIR / ".env"

load_dotenv(ENV_PATH, override=True)
print("DEBUG loaded env from:", ENV_PATH)

import json
import base64
import sqlite3
import csv
import io

from urllib.parse import quote_plus

from fastapi import (
    FastAPI,
    HTTPException,
    Depends,
    Request,
    Form,
    status,
    File,
    UploadFile,
    Query,
    Header
)
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, EmailStr, Field
from starlette.middleware.sessions import SessionMiddleware

import time
from collections import defaultdict, deque

LOGIN_RATE_WINDOW = 60      # segundos
LOGIN_RATE_MAX = 5          # intentos
_login_attempts = defaultdict(deque)

def rate_limit_login(key: str):
    now = time.time()
    q = _login_attempts[key]

    while q and now - q[0] > LOGIN_RATE_WINDOW:
        q.popleft()

    if len(q) >= LOGIN_RATE_MAX:
        raise HTTPException(
            status_code=429,
            detail="Demasiados intentos. Esperá un minuto."
        )

    q.append(now)

# -------------------------
# Paths base
# -------------------------
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "retail.db"
SCHEMA_PATH = BASE_DIR / "schema.sql"
CHECKOUT_BASE_URL = os.getenv(
    "CHECKOUT_BASE_URL", "http://localhost:8001/index.html"
)

# -------------------------
# Config admin (simple)
# -------------------------
ADMIN_USER = os.getenv("ADMIN_USER", "")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

if not ADMIN_USER or not ADMIN_PASSWORD:
    raise RuntimeError("ADMIN_USER / ADMIN_PASSWORD no configurados")

BACKOFFICE_API_KEY = os.getenv("BACKOFFICE_API_KEY", "")
if not BACKOFFICE_API_KEY:
    raise RuntimeError("BACKOFFICE_API_KEY no configurada")

def require_api_key(x_api_key: str = Header(default="")):
    if x_api_key != BACKOFFICE_API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

app = FastAPI(
    title="Retail Backoffice API + Admin",
    description="API + panel admin simple para Retail Agent Demo.",
    version="0.1.0",
)

# Sessions para login
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET_KEY", "dev-only"),
)

# Static & templates
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


# -------------------------
# DB utils
# -------------------------
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    if not DB_PATH.exists():
        print(f"Creando base de datos en {DB_PATH}")
    with get_connection() as conn, open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
        conn.commit()


@app.on_event("startup")
def on_startup():
    init_db()


# -------------------------
# Pydantic models (API JSON)
# -------------------------
class UserCreate(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    segment: Optional[str] = "nuevo"


class User(BaseModel):
    id: int
    name: str
    email: EmailStr
    phone: Optional[str]
    segment: Optional[str]
    created_at: str


class ProductCreate(BaseModel):
    sku: str = Field(..., description="Identificador único del producto")
    name: str
    category: Optional[str] = None
    description: Optional[str] = None
    price: float
    is_offer: bool = False
    stock: int = 0


class Product(ProductCreate):
    id: int
    updated_at: str


class Order(BaseModel):
    id: int
    user_id: int
    cart_id: int
    total: float
    payment_status: str
    created_at: str

class CartAddItemRequest(BaseModel):
    user_id: int
    product_id: int
    quantity: int = 1
    
class CheckoutRequest(BaseModel):
    user_id: int
    email: EmailStr

# -------------------------
# Auth admin (muy simple)
# -------------------------
def get_current_admin(request: Request):
    if request.session.get("is_admin") is True:
        return True
    raise HTTPException(
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        headers={"Location": "/admin/login?error=1"},
    )


# -------------------------
# Rutas HTML: LOGIN + ADMIN
# -------------------------
@app.get("/admin/login", response_class=HTMLResponse)
def admin_login_page(request: Request):
    error_param = request.query_params.get("error")
    error = None
    if error_param == "1":
        error = "Tenés que iniciar sesión para acceder al panel de administración."
    return templates.TemplateResponse(
        "login.html", {"request": request, "error": error}
    )

@app.post("/admin/login", response_class=HTMLResponse)
def admin_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    client_ip = request.client.host if request.client else "unknown"
    rate_limit_login(client_ip)

    if username == ADMIN_USER and password == ADMIN_PASSWORD:
        request.session["is_admin"] = True
        return RedirectResponse(url="/admin", status_code=303)

    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": "Usuario o contraseña incorrectos."},
        status_code=401,
    )


@app.get("/admin/logout")
def admin_logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request, _: bool = Depends(get_current_admin)):
    with get_connection() as conn:
        users_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        products_count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        orders_count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "users_count": users_count,
            "products_count": products_count,
            "orders_count": orders_count,
        },
    )


# -------------------------
# ADMIN HTML: USERS
# -------------------------
@app.get("/admin/users", response_class=HTMLResponse)
def admin_users(
    request: Request,
    q_name: Optional[str] = Query(None),
    q_email: Optional[str] = Query(None),
    q_phone: Optional[str] = Query(None),
    q_segment: Optional[str] = Query(None),
    _: bool = Depends(get_current_admin),
):
    conditions = []
    params = []

    if q_name:
        conditions.append("LOWER(name) LIKE ?")
        params.append(f"%{q_name.lower()}%")
    if q_email:
        conditions.append("email = ?")
        params.append(q_email)
    if q_phone:
        conditions.append("phone = ?")
        params.append(q_phone)
    if q_segment:
        conditions.append("segment = ?")
        params.append(q_segment)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT id, name, email, phone, segment, created_at
            FROM users
            {where}
            ORDER BY created_at DESC
            """,
            params,
        ).fetchall()

    return templates.TemplateResponse(
        "users.html",
        {
            "request": request,
            "users": rows,
            "q_name": q_name,
            "q_email": q_email,
            "q_phone": q_phone,
            "q_segment": q_segment,
        },
    )

@app.get("/admin/users/{user_id}/edit", response_class=HTMLResponse)
def admin_user_edit_page(
    user_id: int,
    request: Request,
    _: bool = Depends(get_current_admin),
):
    with get_connection() as conn:
        user = conn.execute(
            "SELECT id, name, email, phone, segment, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return templates.TemplateResponse(
        "user_edit.html",
        {"request": request, "user": user},
    )
    
@app.post("/admin/users/{user_id}/edit")
def admin_user_edit_save(
    user_id: int,
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(""),
    segment: str = Form("nuevo"),
    _: bool = Depends(get_current_admin),
):
    with get_connection() as conn:
        try:
            cur = conn.execute(
                """
                UPDATE users
                SET name = ?, email = ?, phone = ?, segment = ?
                WHERE id = ?
                """,
                (name, email, phone or None, segment or None, user_id),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            # Email duplicado
            return RedirectResponse(
                url=f"/admin/users/{user_id}/edit",
                status_code=status.HTTP_303_SEE_OTHER,
            )

    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    return RedirectResponse(url="/admin/users", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/admin/users/{user_id}/delete")
def admin_user_delete(
    user_id: int,
    _: bool = Depends(get_current_admin),
):
    with get_connection() as conn:
        cur = conn.cursor()

        user = cur.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        cart_ids = [r["id"] for r in cur.execute(
            "SELECT id FROM carts WHERE user_id = ?",
            (user_id,),
        ).fetchall()]

        if cart_ids:
            placeholders = ",".join(["?"] * len(cart_ids))
            cur.execute(f"DELETE FROM cart_items WHERE cart_id IN ({placeholders})", cart_ids)

        cur.execute("DELETE FROM orders WHERE user_id = ?", (user_id,))
        cur.execute("DELETE FROM carts WHERE user_id = ?", (user_id,))
        cur.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()

    return RedirectResponse(url="/admin/users", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/admin/users", response_class=HTMLResponse)
def admin_create_user(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(""),
    segment: str = Form("nuevo"),
    _: bool = Depends(get_current_admin),
):
    with get_connection() as conn:
        try:
            conn.execute(
                """
                INSERT INTO users (name, email, phone, segment)
                VALUES (?, ?, ?, ?)
                """,
                (name, email, phone or None, segment or "nuevo"),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            pass
    return RedirectResponse(
        url="/admin/users", status_code=status.HTTP_303_SEE_OTHER
    )


@app.post("/admin/users/import", response_class=HTMLResponse)
async def admin_import_users(
    request: Request,
    file: UploadFile = File(...),
    _: bool = Depends(get_current_admin),
):
    content = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    with get_connection() as conn:
        for row in reader:
            name = row.get("name") or row.get("nombre")
            email = row.get("email")
            phone = row.get("phone") or row.get("telefono")
            segment = row.get("segment") or row.get("segmento") or "nuevo"
            if not name or not email:
                continue
            try:
                conn.execute(
                    """
                    INSERT INTO users (name, email, phone, segment)
                    VALUES (?, ?, ?, ?)
                    """,
                    (name, email, phone or None, segment),
                )
            except sqlite3.IntegrityError:
                continue
        conn.commit()
    return RedirectResponse(
        url="/admin/users", status_code=status.HTTP_303_SEE_OTHER
    )


# -------------------------
# ADMIN HTML: PRODUCTS
# -------------------------
@app.get("/admin/products", response_class=HTMLResponse)
def admin_products(
    request: Request,
    q_sku: Optional[str] = Query(None),
    q_name: Optional[str] = Query(None),
    q_category: Optional[str] = Query(None),
    q_offer: Optional[str] = Query(None),  # checkbox -> llega como "on" si está tildado
    _: bool = Depends(get_current_admin),
):
    conditions = []
    params = []

    if q_sku:
        conditions.append("sku = ?")
        params.append(q_sku)
    if q_name:
        conditions.append("LOWER(name) LIKE ?")
        params.append(f"%{q_name.lower()}%")
    if q_category:
        conditions.append("LOWER(category) LIKE ?")
        params.append(f"%{q_category.lower()}%")
    if q_offer:
        conditions.append("is_offer = 1")

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT id, sku, name, category, description, price, is_offer, stock, updated_at
            FROM products
            {where}
            ORDER BY updated_at DESC
            """,
            params,
        ).fetchall()

    return templates.TemplateResponse(
        "products.html",
        {
            "request": request,
            "products": rows,
            "q_sku": q_sku,
            "q_name": q_name,
            "q_category": q_category,
            "q_offer": bool(q_offer),
        },
    )
    
@app.get("/admin/products/{product_id}/edit", response_class=HTMLResponse)
def admin_product_edit_page(
    product_id: int,
    request: Request,
    _: bool = Depends(get_current_admin),
):
    with get_connection() as conn:
        product = conn.execute(
            """
            SELECT id, sku, name, category, description, price, is_offer, stock, updated_at
            FROM products WHERE id = ?
            """,
            (product_id,),
        ).fetchone()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return templates.TemplateResponse(
        "product_edit.html",
        {"request": request, "product": product},
    )


@app.post("/admin/products/{product_id}/edit")
def admin_product_edit_save(
    product_id: int,
    sku: str = Form(...),
    name: str = Form(...),
    price: float = Form(...),
    category: str = Form(""),
    description: str = Form(""),
    stock: int = Form(0),
    is_offer: Optional[str] = Form(None),
    _: bool = Depends(get_current_admin),
):
    with get_connection() as conn:
        try:
            cur = conn.execute(
                """
                UPDATE products
                SET sku = ?, name = ?, category = ?, description = ?, price = ?, is_offer = ?, stock = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    sku,
                    name,
                    category or None,
                    description or None,
                    price,
                    1 if is_offer else 0,
                    stock,
                    product_id,
                ),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            # SKU duplicado
            return RedirectResponse(
                url=f"/admin/products/{product_id}/edit",
                status_code=status.HTTP_303_SEE_OTHER,
            )

    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    return RedirectResponse(url="/admin/products", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/admin/products/{product_id}/delete")
def admin_product_delete(
    product_id: int,
    _: bool = Depends(get_current_admin),
):
    with get_connection() as conn:
        cur = conn.cursor()

        prod = cur.execute("SELECT id FROM products WHERE id = ?", (product_id,)).fetchone()
        if not prod:
            raise HTTPException(status_code=404, detail="Producto no encontrado")

        # Evita problemas de FK
        cur.execute("DELETE FROM cart_items WHERE product_id = ?", (product_id,))
        cur.execute("DELETE FROM products WHERE id = ?", (product_id,))
        conn.commit()

    return RedirectResponse(url="/admin/products", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/admin/products", response_class=HTMLResponse)
def admin_create_product(
    request: Request,
    sku: str = Form(...),
    name: str = Form(...),
    price: float = Form(...),
    category: str = Form(""),
    description: str = Form(""),
    stock: int = Form(0),
    is_offer: Optional[str] = Form(None),
    _: bool = Depends(get_current_admin),
):
    with get_connection() as conn:
        try:
            conn.execute(
                """
                INSERT INTO products (sku, name, category, description, price, is_offer, stock)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sku,
                    name,
                    category or None,
                    description or None,
                    price,
                    1 if is_offer else 0,
                    stock,
                ),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            pass
    return RedirectResponse(
        url="/admin/products", status_code=status.HTTP_303_SEE_OTHER
    )


@app.post("/admin/products/import", response_class=HTMLResponse)
async def admin_import_products(
    request: Request,
    file: UploadFile = File(...),
    _: bool = Depends(get_current_admin),
):
    content = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    with get_connection() as conn:
        for row in reader:
            sku = row.get("sku")
            name = row.get("name") or row.get("nombre")
            price = row.get("price") or row.get("precio")
            category = row.get("category") or row.get("categoria")
            description = row.get("description") or row.get("descripcion")
            stock = row.get("stock") or 0
            is_offer_val = row.get("is_offer") or row.get("oferta") or "0"
            if not sku or not name or not price:
                continue
            try:
                price = float(price)
            except ValueError:
                continue
            try:
                stock = int(stock)
            except ValueError:
                stock = 0
            is_offer = str(is_offer_val).strip().lower() in (
                "1",
                "true",
                "sí",
                "si",
                "yes",
                "y",
            )
            try:
                conn.execute(
                """
                INSERT INTO products (sku, name, category, description, price, is_offer, stock)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sku,
                    name,
                    category or None,
                    description or None,
                    price,
                    1 if is_offer else 0,
                    stock,
                ),
            )
            except sqlite3.IntegrityError:
                continue
        conn.commit()
    return RedirectResponse(
        url="/admin/products", status_code=status.HTTP_303_SEE_OTHER
    )


# -------------------------
# ADMIN HTML: ORDERS & CARTS
# -------------------------
@app.get("/admin/orders", response_class=HTMLResponse)
def admin_orders(
    request: Request,
    q_user: Optional[str] = Query(None),
    q_email: Optional[str] = Query(None),
    q_status: Optional[str] = Query(None),
    _: bool = Depends(get_current_admin),
):
    conditions = []
    params = []

    if q_user:
        conditions.append("LOWER(u.name) LIKE ?")
        params.append(f"%{q_user.lower()}%")
    if q_email:
        conditions.append("u.email = ?")
        params.append(q_email)
    if q_status:
        conditions.append("o.payment_status = ?")
        params.append(q_status)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT
                o.id, o.user_id, u.name AS user_name, u.email AS user_email,
                o.cart_id, o.total, o.payment_status, o.created_at
            FROM orders o
            JOIN users u ON u.id = o.user_id
            {where}
            ORDER BY o.created_at DESC
            """,
            params,
        ).fetchall()

    return templates.TemplateResponse(
        "orders.html",
        {"request": request, "orders": rows, "q_user": q_user, "q_email": q_email, "q_status": q_status},
    )

@app.get("/admin/orders/{order_id}/edit", response_class=HTMLResponse)
def admin_order_edit_page(
    order_id: int,
    request: Request,
    _: bool = Depends(get_current_admin),
):
    with get_connection() as conn:
        order = conn.execute(
            """
            SELECT
              o.id, o.user_id, u.name AS user_name, u.email AS user_email,
              o.cart_id, o.total, o.payment_status, o.created_at
            FROM orders o
            JOIN users u ON u.id = o.user_id
            WHERE o.id = ?
            """,
            (order_id,),
        ).fetchone()
    if not order:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    return templates.TemplateResponse("order_edit.html", {"request": request, "order": order})

@app.post("/admin/orders/{order_id}/edit")
def admin_order_edit_save(
    order_id: int,
    payment_status: str = Form(...),
    _: bool = Depends(get_current_admin),
):
    with get_connection() as conn:
        cur = conn.execute(
            "UPDATE orders SET payment_status = ? WHERE id = ?",
            (payment_status, order_id),
        )
        conn.commit()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    return RedirectResponse(url=f"/admin/orders/{order_id}", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/admin/orders/{order_id}/delete")
def admin_order_delete(
    order_id: int,
    _: bool = Depends(get_current_admin),
):
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM orders WHERE id = ?", (order_id,))
        conn.commit()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    return RedirectResponse(url="/admin/orders", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/admin/orders/{order_id}", response_class=HTMLResponse)
def admin_order_detail(
    order_id: int,
    request: Request,
    _: bool = Depends(get_current_admin),
):
    with get_connection() as conn:
        order = conn.execute(
            """
            SELECT
                o.id,
                o.user_id,
                u.name AS user_name,
                u.email AS user_email,
                o.cart_id,
                o.total,
                o.payment_status,
                o.created_at
            FROM orders o
            JOIN users u ON u.id = o.user_id
            WHERE o.id = ?
            """,
            (order_id,),
        ).fetchone()
        if not order:
            raise HTTPException(status_code=404, detail="Orden no encontrada")
        items = conn.execute(
            """
            SELECT
                p.sku,
                p.name AS product_name,
                ci.quantity,
                ci.unit_price,
                (ci.quantity * ci.unit_price) AS line_total
            FROM cart_items ci
            JOIN products p ON p.id = ci.product_id
            WHERE ci.cart_id = ?
            ORDER BY p.name
            """,
            (order["cart_id"],),
        ).fetchall()
    return templates.TemplateResponse(
        "order_detail.html",
        {"request": request, "order": order, "items": items},
    )


@app.get("/admin/carts", response_class=HTMLResponse)
def admin_carts(
    request: Request,
    q_user: Optional[str] = Query(None),
    q_email: Optional[str] = Query(None),
    q_status: Optional[str] = Query(None),
    _: bool = Depends(get_current_admin),
):
    conditions = []
    params = []

    if q_user:
        conditions.append("LOWER(u.name) LIKE ?")
        params.append(f"%{q_user.lower()}%")
    if q_email:
        conditions.append("u.email = ?")
        params.append(q_email)
    if q_status:
        conditions.append("c.status = ?")
        params.append(q_status)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT
                c.id, c.user_id, u.name AS user_name, u.email AS user_email,
                c.status, c.created_at, c.updated_at,
                COALESCE(SUM(ci.quantity * ci.unit_price), 0) AS total,
                COALESCE(SUM(ci.quantity), 0) AS items_count
            FROM carts c
            JOIN users u ON u.id = c.user_id
            LEFT JOIN cart_items ci ON ci.cart_id = c.id
            {where}
            GROUP BY c.id
            ORDER BY c.created_at DESC
            """,
            params,
        ).fetchall()

    return templates.TemplateResponse(
        "carts.html",
        {"request": request, "carts": rows, "q_user": q_user, "q_email": q_email, "q_status": q_status},
    )
    
@app.get("/admin/carts/{cart_id}/edit", response_class=HTMLResponse)
def admin_cart_edit_page(
    cart_id: int,
    request: Request,
    _: bool = Depends(get_current_admin),
):
    with get_connection() as conn:
        cart = conn.execute(
            """
            SELECT
                c.id, c.user_id, u.name AS user_name, u.email AS user_email,
                c.status, c.created_at, c.updated_at,
                COALESCE(SUM(ci.quantity * ci.unit_price), 0) AS total,
                COALESCE(SUM(ci.quantity), 0) AS items_count
            FROM carts c
            JOIN users u ON u.id = c.user_id
            LEFT JOIN cart_items ci ON ci.cart_id = c.id
            WHERE c.id = ?
            GROUP BY c.id
            """,
            (cart_id,),
        ).fetchone()
    if not cart:
        raise HTTPException(status_code=404, detail="Carrito no encontrado")
    return templates.TemplateResponse("cart_edit.html", {"request": request, "cart": cart})

@app.post("/admin/carts/{cart_id}/edit")
def admin_cart_edit_save(
    cart_id: int,
    status_val: str = Form(..., alias="status"),
    _: bool = Depends(get_current_admin),
):
    with get_connection() as conn:
        cur = conn.execute(
            "UPDATE carts SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status_val, cart_id),
        )
        conn.commit()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Carrito no encontrado")
    return RedirectResponse(url=f"/admin/carts/{cart_id}", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/admin/carts/{cart_id}/delete")
def admin_cart_delete(
    cart_id: int,
    _: bool = Depends(get_current_admin),
):
    with get_connection() as conn:
        cur = conn.cursor()
        cart = cur.execute("SELECT id FROM carts WHERE id = ?", (cart_id,)).fetchone()
        if not cart:
            raise HTTPException(status_code=404, detail="Carrito no encontrado")
        cur.execute("DELETE FROM cart_items WHERE cart_id = ?", (cart_id,))
        cur.execute("DELETE FROM carts WHERE id = ?", (cart_id,))
        conn.commit()
    return RedirectResponse(url="/admin/carts", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/admin/carts/{cart_id}", response_class=HTMLResponse)
def admin_cart_detail(cart_id: int, request: Request, _: bool = Depends(get_current_admin)):
    with get_connection() as conn:
        cart = conn.execute(
            """
            SELECT
                c.id,
                c.user_id,
                u.name AS user_name,
                u.email AS user_email,
                c.status,
                c.created_at,
                c.updated_at,
                COALESCE(SUM(ci.quantity * ci.unit_price), 0) AS total,
                COALESCE(SUM(ci.quantity), 0) AS items_count
            FROM carts c
            JOIN users u ON u.id = c.user_id
            LEFT JOIN cart_items ci ON ci.cart_id = c.id
            WHERE c.id = ?
            GROUP BY c.id
            """,
            (cart_id,),
        ).fetchone()
        if not cart:
            raise HTTPException(status_code=404, detail="Carrito no encontrado")
        items = conn.execute(
            """
            SELECT
                p.sku,
                p.name AS product_name,
                ci.quantity,
                ci.unit_price,
                (ci.quantity * ci.unit_price) AS line_total
            FROM cart_items ci
            JOIN products p ON p.id = ci.product_id
            WHERE ci.cart_id = ?
            ORDER BY p.name
            """,
            (cart_id,),
        ).fetchall()
    return templates.TemplateResponse(
        "cart_detail.html",
        {"request": request, "cart": cart, "items": items},
    )


# -------------------------
# Helpers para carritos
# -------------------------
def build_cart_summary(conn: sqlite3.Connection, cart_id: int) -> Dict[str, Any]:
    rows = conn.execute(
        """
        SELECT
            ci.product_id,
            p.name AS product_name,
            ci.quantity,
            ci.unit_price,
            (ci.quantity * ci.unit_price) AS line_total
        FROM cart_items ci
        JOIN products p ON p.id = ci.product_id
        WHERE ci.cart_id = ?
        ORDER BY p.name
        """,
        (cart_id,),
    ).fetchall()
    items = []
    total = 0.0
    for r in rows:
        item = {
            "product_id": r["product_id"],
            "name": r["product_name"],
            "quantity": r["quantity"],
            "unit_price": r["unit_price"],
            "line_total": r["line_total"],
        }
        items.append(item)
        total += float(r["line_total"])
    return {
        "cart_id": cart_id,
        "items": items,
        "total": total,
    }


# -------------------------
# API JSON: USERS
# -------------------------
@app.post("/users", response_model=User)
def create_user(user: UserCreate, _: bool = Depends(require_api_key)):
    with get_connection() as conn:
        try:
            cur = conn.execute(
                """
                INSERT INTO users (name, email, phone, segment)
                VALUES (?, ?, ?, ?)
                """,
                (user.name, user.email, user.phone, user.segment),
            )
            conn.commit()
            user_id = cur.lastrowid
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=400, detail="Email ya registrado")
        row = conn.execute(
            "SELECT id, name, email, phone, segment, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    return User(**dict(row))


@app.get("/users", response_model=List[User])
def list_users(_: bool = Depends(require_api_key)):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name, email, phone, segment, created_at FROM users "
            "ORDER BY created_at DESC"
        ).fetchall()
    return [User(**dict(r)) for r in rows]

@app.get("/users/by_email", response_model=User)
def get_user_by_email(email: str, _: bool = Depends(require_api_key)):
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, name, email, phone, segment, created_at
            FROM users
            WHERE email = ?
            """,
            (email,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return User(**dict(row))

@app.get("/users/search", response_model=List[User])
def search_users(
    email: Optional[str] = Query(None),
    phone: Optional[str] = Query(None),
    name: Optional[str] = Query(None),
    _: bool = Depends(require_api_key)
):
    """
    Busca usuarios por uno o más criterios usando lógica OR.
    Devuelve TODOS los usuarios que coincidan con al menos uno de los criterios.
    """
    conditions = []
    params = []
    if email:
        conditions.append("email = ?")
        params.append(email)
    if phone:
        conditions.append("phone = ?")
        params.append(phone)
    if name:
        conditions.append("LOWER(name) LIKE ?")
        params.append(f"%{name.lower()}%")
    if not conditions:
        return []
    sql = f"""
        SELECT id, name, email, phone, segment, created_at
        FROM users
        WHERE {' OR '.join(conditions)}
        ORDER BY created_at DESC
    """
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [User(**dict(r)) for r in rows]

@app.get("/users/{user_id}", response_model=User)
def get_user(user_id: int, _: bool = Depends(require_api_key)):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, name, email, phone, segment, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return User(**dict(row))


# -------------------------
# API JSON: CARTS
# -------------------------
@app.post("/carts/add_item")
def api_cart_add_item(payload: CartAddItemRequest, _: bool = Depends(require_api_key)) -> Dict[str, Any]:
    if payload.quantity <= 0:
        raise HTTPException(status_code=400, detail="La cantidad debe ser mayor a 0.")
    with get_connection() as conn:
        cur = conn.cursor()
        user = cur.execute(
            "SELECT id, name, email FROM users WHERE id = ?",
            (payload.user_id,),
        ).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        product = cur.execute(
            "SELECT id, price, stock FROM products WHERE id = ?",
            (payload.product_id,),
        ).fetchone()
        if not product:
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        if product["stock"] is not None and product["stock"] < payload.quantity:
            raise HTTPException(status_code=400, detail="No hay stock suficiente")
        cart = cur.execute(
            """
            SELECT id
            FROM carts
            WHERE user_id = ? AND status = 'open'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (payload.user_id,),
        ).fetchone()
        if cart:
            cart_id = cart["id"]
        else:
            cur.execute(
                "INSERT INTO carts (user_id, status) VALUES (?, 'open')",
                (payload.user_id,),
            )
            cart_id = cur.lastrowid
        existing_item = cur.execute(
            """
            SELECT id, quantity
            FROM cart_items
            WHERE cart_id = ? AND product_id = ?
            """,
            (cart_id, payload.product_id),
        ).fetchone()
        if existing_item:
            new_qty = existing_item["quantity"] + payload.quantity
            cur.execute(
                """
                UPDATE cart_items
                SET quantity = ?, unit_price = ?
                WHERE id = ?
                """,
                (new_qty, product["price"], existing_item["id"]),
            )
        else:
            cur.execute(
                """
                INSERT INTO cart_items (cart_id, product_id, quantity, unit_price)
                VALUES (?, ?, ?, ?)
                """,
                (cart_id, payload.product_id, payload.quantity, product["price"]),
            )
        cur.execute(
            "UPDATE carts SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (cart_id,),
        )
        conn.commit()
        summary = build_cart_summary(conn, cart_id)
    return {
        "cart_id": summary["cart_id"],
        "user_id": payload.user_id,
        "items": summary["items"],
        "total": summary["total"],
    }


@app.get("/carts/summary")
def api_cart_summary(user_id: int = Query(...), _: bool = Depends(require_api_key)) -> Dict[str, Any]:
    with get_connection() as conn:
        cart = conn.execute(
            """
            SELECT id
            FROM carts
            WHERE user_id = ? AND status = 'open'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
        if not cart:
            return {
                "cart_id": None,
                "user_id": user_id,
                "items": [],
                "total": 0.0,
            }
        summary = build_cart_summary(conn, cart["id"])
    return {
        "cart_id": summary["cart_id"],
        "user_id": user_id,
        "items": summary["items"],
        "total": summary["total"],
    }

class CartClearRequest(BaseModel):
    user_id: int

@app.post("/carts/clear")
def api_cart_clear(payload: CartClearRequest, _: bool = Depends(require_api_key)) -> Dict[str, Any]:
    with get_connection() as conn:
        cur = conn.cursor()

        # Buscar carrito abierto más reciente
        cart = cur.execute(
            """
            SELECT id
            FROM carts
            WHERE user_id = ? AND status = 'open'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (payload.user_id,),
        ).fetchone()

        if not cart:
            # No hay carrito abierto → devolvemos "ok" con carrito vacío
            return {
                "status": "success",
                "message": "No había carrito abierto. Ya está vacío.",
                "cart_id": None,
                "user_id": payload.user_id,
                "items": [],
                "total": 0.0,
            }

        cart_id = cart["id"]

        # Borrar items del carrito abierto
        cur.execute("DELETE FROM cart_items WHERE cart_id = ?", (cart_id,))
        cur.execute(
            "UPDATE carts SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (cart_id,),
        )
        conn.commit()

        # Resumen vacío post-clear
        return {
            "status": "success",
            "message": "Carrito reiniciado.",
            "cart_id": cart_id,
            "user_id": payload.user_id,
            "items": [],
            "total": 0.0,
        }

# -------------------------
# API JSON: CHECKOUT
# -------------------------
@app.post("/orders/checkout")
def api_checkout(payload: CheckoutRequest, _: bool = Depends(require_api_key)) -> Dict[str, Any]:
    with get_connection() as conn:
        cur = conn.cursor()
        user = cur.execute(
            "SELECT id, name, email FROM users WHERE id = ?",
            (payload.user_id,),
        ).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        cart = cur.execute(
            """
            SELECT id
            FROM carts
            WHERE user_id = ? AND status = 'open'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (payload.user_id,),
        ).fetchone()
        if not cart:
            raise HTTPException(
                status_code=400,
                detail="El usuario no tiene un carrito abierto para checkout.",
            )
        cart_id = cart["id"]
        rows = cur.execute(
            """
            SELECT
                p.id   AS product_id,
                p.name AS product_name,
                ci.quantity,
                ci.unit_price,
                (ci.quantity * ci.unit_price) AS line_total
            FROM cart_items ci
            JOIN products p ON p.id = ci.product_id
            WHERE ci.cart_id = ?
            """,
            (cart_id,),
        ).fetchall()
        if not rows:
            raise HTTPException(status_code=400, detail="El carrito está vacío.")
        items: List[Dict[str, Any]] = []
        total = 0.0
        for r in rows:
            line = {
                "product_id": r["product_id"],
                "name": r["product_name"],
                "quantity": r["quantity"],
                "unit_price": r["unit_price"],
                "line_total": r["line_total"],
            }
            items.append(line)
            total += float(r["line_total"])
        cur.execute(
            """
            INSERT INTO orders (user_id, cart_id, total, payment_status)
            VALUES (?, ?, ?, ?)
            """,
            (payload.user_id, cart_id, total, "pending"),
        )
        order_id = cur.lastrowid
        cur.execute(
            "UPDATE carts SET status = 'checked_out', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (cart_id,),
        )
        conn.commit()
        user_name = user["name"]
        user_email = user["email"] or payload.email
        items_payload = base64.urlsafe_b64encode(
            json.dumps(items).encode("utf-8")
        ).decode("utf-8")
        payment_url = (
            f"{CHECKOUT_BASE_URL}"
            f"?user_id={quote_plus(str(user['id']))}"
            f"&name={quote_plus(user_name)}"
            f"&email={quote_plus(user_email)}"
            f"&amount={total:.2f}"
            f"&items={items_payload}"
        )
    return {
        "order_id": order_id,
        "cart_id": cart_id,
        "total": total,
        "payment_status": "pending",
        "payment_url": payment_url,
    }

# Base del checkout frontend (index.html)
CHECKOUT_FRONTEND_BASE = os.getenv(
    "CHECKOUT_FRONTEND_URL",
    "http://localhost:8001/index.html"
)

@app.get("/checkout/{order_id}")
def redirect_checkout(order_id: int,):
    """
    Redirige a la página de checkout (index.html) armando internamente
    el querystring largo a partir de la orden en la base.

    URL corta que verá el usuario:
      http://localhost:8000/checkout/{order_id}
    """
    with get_connection() as conn:
        # Buscar la orden
        order = conn.execute(
            """
            SELECT id, user_id, cart_id, total, payment_status, created_at
            FROM orders
            WHERE id = ?
            """,
            (order_id,),
        ).fetchone()

        if not order:
            raise HTTPException(status_code=404, detail="Orden no encontrada")

        # Traer el usuario
        user = conn.execute(
            """
            SELECT id, name, email
            FROM users
            WHERE id = ?
            """,
            (order["user_id"],),
        ).fetchone()

        if not user:
            raise HTTPException(status_code=404, detail="Usuario de la orden no encontrado")

        # Traer ítems del carrito
        items_rows = conn.execute(
            """
            SELECT
                ci.product_id,
                p.name AS product_name,
                ci.quantity,
                ci.unit_price,
                (ci.quantity * ci.unit_price) AS line_total
            FROM cart_items ci
            JOIN products p ON p.id = ci.product_id
            WHERE ci.cart_id = ?
            ORDER BY p.name
            """,
            (order["cart_id"],),
        ).fetchall()

    items = [
        {
            "product_id": r["product_id"],
            "name": r["product_name"],
            "quantity": r["quantity"],
            "unit_price": float(r["unit_price"]),
            "line_total": float(r["line_total"]),
        }
        for r in items_rows
    ]

    # Armamos el JSON de items y lo encodeamos en base64 URL-safe
    items_json = json.dumps(items, ensure_ascii=False)
    items_b64 = base64.urlsafe_b64encode(items_json.encode("utf-8")).decode("utf-8")

    # Armamos el querystring como antes, pero acá adentro
    params = {
        "user_id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "amount": f"{float(order['total']):.2f}",
        "items": items_b64,
    }

    query_string = "&".join(
        f"{key}={quote_plus(str(value))}" for key, value in params.items()
    )

    final_url = f"{CHECKOUT_FRONTEND_BASE}?{query_string}"

    return RedirectResponse(url=final_url)


# -------------------------
# API JSON: PRODUCTS
# -------------------------
@app.post("/products", response_model=Product)
def api_create_product(product: ProductCreate, _: bool = Depends(require_api_key)):
    with get_connection() as conn:
        try:
            cur = conn.execute(
                """
                INSERT INTO products (sku, name, category, description, price, is_offer, stock)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    product.sku,
                    product.name,
                    product.category,
                    product.description,
                    product.price,
                    1 if product.is_offer else 0,
                    product.stock,
                ),
            )
            conn.commit()
            product_id = cur.lastrowid
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=400, detail="SKU ya existente")
        row = conn.execute(
            """
            SELECT id, sku, name, category, description, price, is_offer, stock, updated_at
            FROM products WHERE id = ?
            """,
            (product_id,),
        ).fetchone()
    data = dict(row)
    data["is_offer"] = bool(data["is_offer"])
    return Product(**data)


@app.get("/products", response_model=List[Product])
def api_list_products(_: bool = Depends(require_api_key)):
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, sku, name, category, description, price, is_offer, stock, updated_at
            FROM products
            ORDER BY updated_at DESC
            """
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["is_offer"] = bool(d["is_offer"])
        result.append(Product(**d))
    return result


@app.get("/products/{product_id}", response_model=Product)
def api_get_product(product_id: int, _: bool = Depends(require_api_key)):
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, sku, name, category, description, price, is_offer, stock, updated_at
            FROM products WHERE id = ?
            """,
            (product_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    d = dict(row)
    d["is_offer"] = bool(d["is_offer"])
    return Product(**d)


# -------------------------
# API JSON: ORDERS
# -------------------------
@app.get("/orders", response_model=List[Order])
def api_list_orders(_: bool = Depends(require_api_key)):
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, user_id, cart_id, total, payment_status, created_at
            FROM orders
            ORDER BY created_at DESC
            """
        ).fetchall()
    return [Order(**dict(r)) for r in rows]

@app.get("/orders/last")
def api_get_last_order(user_id: int = Query(...), _: bool = Depends(require_api_key)) -> Dict[str, Any]:
    """
    Devuelve el último pedido de un usuario (si existe), con sus ítems.
    """
    with get_connection() as conn:
        order = conn.execute(
            """
            SELECT id, user_id, cart_id, total, payment_status, created_at
            FROM orders
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()

        if not order:
            return {
                "status": "not_found",
                "message": "El usuario no tiene pedidos previos."
            }

        items_rows = conn.execute(
            """
            SELECT
                p.name AS product_name,
                ci.quantity
            FROM cart_items ci
            JOIN products p ON p.id = ci.product_id
            WHERE ci.cart_id = ?
            ORDER BY p.name
            """,
            (order["cart_id"],),
        ).fetchall()

        items = [
            {
                "name": r["product_name"],
                "quantity": r["quantity"],
            }
            for r in items_rows
        ]

        return {
            "status": "found",
            "order": {
                "id": order["id"],
                "user_id": order["user_id"],
                "cart_id": order["cart_id"],
                "total": float(order["total"]),
                "payment_status": order["payment_status"],
                "created_at": order["created_at"],
                "items": items,
            },
        }

@app.get("/orders/by_user")
def api_orders_by_user(
    user_id: int = Query(...),
    limit: int = Query(3, ge=1, le=50), _: bool = Depends(require_api_key)
):
    """
    Devuelve los últimos pedidos de un usuario (incluye items).
    Pensado para que el agente pueda responder "¿cómo va mi último pedido?"
    o "¿qué pedí la vez pasada?".
    """
    with get_connection() as conn:
        orders = conn.execute(
            """
            SELECT id, user_id, cart_id, total, payment_status, created_at
            FROM orders
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()

        result = []
        for o in orders:
            items_rows = conn.execute(
                """
                SELECT
                    p.sku,
                    p.name AS product_name,
                    ci.quantity,
                    ci.unit_price,
                    (ci.quantity * ci.unit_price) AS line_total
                FROM cart_items ci
                JOIN products p ON p.id = ci.product_id
                WHERE ci.cart_id = ?
                ORDER BY p.name
                """,
                (o["cart_id"],),
            ).fetchall()

            items = []
            for r in items_rows:
                items.append(
                    {
                        "sku": r["sku"],
                        "name": r["product_name"],
                        "quantity": r["quantity"],
                        "unit_price": float(r["unit_price"]),
                        "line_total": float(r["line_total"]),
                    }
                )

            result.append(
                {
                    "id": o["id"],
                    "user_id": o["user_id"],
                    "cart_id": o["cart_id"],
                    "total": float(o["total"]),
                    "payment_status": o["payment_status"],
                    "created_at": o["created_at"],
                    "items": items,
                }
            )

    return result

@app.get("/orders/{order_id}", response_model=Order)
def api_get_order(order_id: int, _: bool = Depends(require_api_key)):
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, user_id, cart_id, total, payment_status, created_at
            FROM orders
            WHERE id = ?
            """,
            (order_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    return Order(**dict(row))



@app.get("/orders/payment_link")
def api_get_order_payment_link(order_id: int = Query(...), _: bool = Depends(require_api_key)) -> Dict[str, Any]:
    """
    Devuelve el link de pago para una orden ya creada.
    Si ya existe, lo devuelve.
    Si no existe, genera uno simple basado en el checkout.
    """

    with get_connection() as conn:
        order = conn.execute(
            """
            SELECT id, user_id, cart_id, total, payment_status
            FROM orders
            WHERE id = ?
            """,
            (order_id,),
        ).fetchone()

        if not order:
            return {
                "status": "not_found",
                "message": "No existe esa orden."
            }

        # Generamos un link simple basado en los datos de la orden
        # (para demo es perfecto)
        payment_url = (
            f"http://localhost:8001/index.html"
            f"?order_id={order['id']}&user_id={order['user_id']}&total={order['total']}"
        )

        return {
            "status": "found",
            "order_id": order_id,
            "payment_url": payment_url,
        }
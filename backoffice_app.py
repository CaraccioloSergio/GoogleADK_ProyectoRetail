from pathlib import Path
from typing import List, Optional, Dict, Any 

import os
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
    Query
)
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, EmailStr, Field
from starlette.middleware.sessions import SessionMiddleware
from urllib.parse import quote_plus

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
ADMIN_USER = "admin"
ADMIN_PASSWORD = "admin123"  # para demo; en prod, ponelo en .env

app = FastAPI(
    title="Retail Backoffice API + Admin",
    description="API + panel admin simple para Retail Agent Demo.",
    version="0.1.0",
)

# Sessions para login
app.add_middleware(SessionMiddleware, secret_key="super-secret-demo-key")

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

    # Si no está logueado, lo mando al login con un query param de error
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
    if username == ADMIN_USER and password == ADMIN_PASSWORD:
        request.session["is_admin"] = True
        return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)

    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": "Usuario o contraseña incorrectos."},
        status_code=status.HTTP_401_UNAUTHORIZED,
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
def admin_users(request: Request, _: bool = Depends(get_current_admin)):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name, email, phone, segment, created_at "
            "FROM users ORDER BY created_at DESC"
        ).fetchall()

    return templates.TemplateResponse(
        "users.html",
        {"request": request, "users": rows},
    )


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
            # Email duplicado: por ahora lo ignoramos en el admin simple
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
                # si el email ya existe, lo salteamos
                continue
        conn.commit()

    return RedirectResponse(
        url="/admin/users", status_code=status.HTTP_303_SEE_OTHER
    )


# -------------------------
# ADMIN HTML: PRODUCTS
# -------------------------
@app.get("/admin/products", response_class=HTMLResponse)
def admin_products(request: Request, _: bool = Depends(get_current_admin)):
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, sku, name, category, description, price, is_offer, stock, updated_at
            FROM products
            ORDER BY updated_at DESC
            """
        ).fetchall()

    return templates.TemplateResponse(
        "products.html",
        {"request": request, "products": rows},
    )


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
            # SKU duplicado
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
                # SKU ya existe → por ahora lo salteamos
                continue

        conn.commit()

    return RedirectResponse(
        url="/admin/products", status_code=status.HTTP_303_SEE_OTHER
    )


# -------------------------
# ADMIN HTML: ORDERS & CARTS
# -------------------------
@app.get("/admin/orders", response_class=HTMLResponse)
def admin_orders(request: Request, _: bool = Depends(get_current_admin)):
    with get_connection() as conn:
        rows = conn.execute(
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
            ORDER BY o.created_at DESC
            """
        ).fetchall()

    return templates.TemplateResponse(
        "orders.html",
        {"request": request, "orders": rows},
    )

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
def admin_carts(request: Request, _: bool = Depends(get_current_admin)):
    with get_connection() as conn:
        rows = conn.execute(
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
            GROUP BY c.id
            ORDER BY c.created_at DESC
            """
        ).fetchall()

    return templates.TemplateResponse(
        "carts.html",
        {"request": request, "carts": rows},
    )


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
def _get_open_cart_id(conn: sqlite3.Connection, user_id: int) -> Optional[int]:
    row = conn.execute(
        """
        SELECT id
        FROM carts
        WHERE user_id = ? AND status = 'open'
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()
    return row["id"] if row else None


def _get_or_create_open_cart_id(conn: sqlite3.Connection, user_id: int) -> int:
    cart_id = _get_open_cart_id(conn, user_id)
    if cart_id is not None:
        return cart_id

    cur = conn.execute(
        "INSERT INTO carts (user_id, status) VALUES (?, 'open')",
        (user_id,),
    )
    return cur.lastrowid


def _build_cart_summary(conn: sqlite3.Connection, cart_id: int) -> dict:
    rows = conn.execute(
        """
        SELECT
            p.id            AS product_id,
            p.name          AS product_name,
            ci.quantity     AS quantity,
            ci.unit_price   AS unit_price,
            ci.quantity * ci.unit_price AS line_total
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
        d = dict(r)
        total += float(d["line_total"])
        items.append(
            {
                "product_id": d["product_id"],
                "product_name": d["product_name"],
                "quantity": d["quantity"],
                "unit_price": float(d["unit_price"]),
                "line_total": float(d["line_total"]),
            }
        )

    return {
        "cart_id": cart_id,
        "items": items,
        "total": total,
    }

def build_cart_summary(conn: sqlite3.Connection, cart_id: int) -> Dict[str, Any]:
    """
    Devuelve un dict con:
      - cart_id
      - items: [{product_id, name, quantity, unit_price, line_total}, ...]
      - total: float
    """
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
def create_user(user: UserCreate):
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
def list_users():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name, email, phone, segment, created_at FROM users "
            "ORDER BY created_at DESC"
        ).fetchall()
    return [User(**dict(r)) for r in rows]


@app.get("/users/{user_id}", response_model=User)
def get_user(user_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, name, email, phone, segment, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return User(**dict(row))

@app.get("/users/by_email", response_model=User)
def get_user_by_email(email: str):
    """
    Devuelve un usuario buscado por email.
    Pensado para que el agente pueda hacer identify_or_create:
    primero busca por email, si no existe lo crea.
    """
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
):
    """
    Busca usuarios por uno o más criterios:
    - email (match exacto)
    - phone (match exacto)
    - name (búsqueda parcial, LIKE)
    """
    sql = """
        SELECT id, name, email, phone, segment, created_at
        FROM users
        WHERE 1=1
    """
    params = []

    if email:
        sql += " AND email = ?"
        params.append(email)

    if phone:
        sql += " AND phone = ?"
        params.append(phone)

    if name:
        sql += " AND LOWER(name) LIKE ?"
        params.append(f"%{name.lower()}%")

    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()

    return [User(**dict(r)) for r in rows]

# -------------------------
# API JSON: CARTS
# -------------------------

@app.post("/carts/add_item")
def api_cart_add_item(payload: CartAddItemRequest) -> Dict[str, Any]:
    """
    Agrega un ítem al carrito "open" del usuario.
    Si no existe carrito open, lo crea.
    Request body:
      { "user_id": int, "product_id": int, "quantity": int }
    Response:
      { "cart_id": int, "items": [...], "total": float }
    """
    if payload.quantity <= 0:
        raise HTTPException(status_code=400, detail="La cantidad debe ser mayor a 0.")

    with get_connection() as conn:
        cur = conn.cursor()

        # 1) Usuario
        user = cur.execute(
            "SELECT id, name, email FROM users WHERE id = ?",
            (payload.user_id,),
        ).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        # 2) Producto
        product = cur.execute(
            "SELECT id, price, stock FROM products WHERE id = ?",
            (payload.product_id,),
        ).fetchone()
        if not product:
            raise HTTPException(status_code=404, detail="Producto no encontrado")

        # (opcional) chequeo simple de stock
        if product["stock"] is not None and product["stock"] < payload.quantity:
            raise HTTPException(status_code=400, detail="No hay stock suficiente")

        # 3) Carrito open del usuario (o crear uno nuevo)
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

        # 4) Insertar / actualizar item
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

        # 5) Actualizar timestamp del carrito
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
def api_cart_summary(user_id: int = Query(...)) -> Dict[str, Any]:
    """
    Devuelve el resumen del carrito 'open' de un usuario.
    Si no tiene carrito, devuelve items vacíos y total 0.
    """
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

# -------------------------
# API JSON: CHECKOUT
# -------------------------

@app.post("/orders/checkout")
def api_checkout(payload: CheckoutRequest) -> Dict[str, Any]:
    """
    Cierra el carrito 'open' del usuario, crea una orden y
    genera la URL de pago para el checkout_web.

    Request body:
      { "user_id": int, "email": str }

    Response:
      {
        "order_id": int,
        "cart_id": int,
        "total": float,
        "payment_status": "pending",
        "payment_url": str
      }
    """
    with get_connection() as conn:
        cur = conn.cursor()

        # 1) Usuario
        user = cur.execute(
            "SELECT id, name, email FROM users WHERE id = ?",
            (payload.user_id,),
        ).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        # 2) Carrito open
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

        # 3) Items del carrito
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

        # 4) Crear la orden
        cur.execute(
            """
            INSERT INTO orders (user_id, cart_id, total, payment_status)
            VALUES (?, ?, ?, ?)
            """,
            (payload.user_id, cart_id, total, "pending"),
        )
        order_id = cur.lastrowid

        # 5) Marcar carrito como 'checked_out'
        cur.execute(
            "UPDATE carts SET status = 'checked_out', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (cart_id,),
        )

        conn.commit()

        # 6) Generar payment_url para el checkout_web
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


# -------------------------
# API JSON: PRODUCTS
# -------------------------
@app.post("/products", response_model=Product)
def api_create_product(product: ProductCreate):
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
def api_list_products():
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
def api_get_product(product_id: int):
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
# API JSON: ORDERS (solo lectura)
# -------------------------
@app.get("/orders", response_model=List[Order])
def api_list_orders():
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, user_id, cart_id, total, payment_status, created_at
            FROM orders
            ORDER BY created_at DESC
            """
        ).fetchall()
    return [Order(**dict(r)) for r in rows]

# -------------------------
# API JSON: CARTS & CHECKOUT (para el agente)
# -------------------------

class AddItemRequest(BaseModel):
    user_id: int
    product_id: int
    quantity: int = 1


class CheckoutFromAgentRequest(BaseModel):
    user_id: int
    email: EmailStr


@app.post("/carts/add_item")
def api_add_item_to_cart(payload: AddItemRequest):
    if payload.quantity <= 0:
        raise HTTPException(status_code=400, detail="Cantidad debe ser > 0")

    with get_connection() as conn:
        # Validar producto
        product = conn.execute(
            "SELECT id, price FROM products WHERE id = ?",
            (payload.product_id,),
        ).fetchone()
        if not product:
            raise HTTPException(status_code=404, detail="Producto no encontrado")

        cart_id = _get_or_create_open_cart_id(conn, payload.user_id)

        # Ver si ya hay una línea para ese producto
        existing = conn.execute(
            """
            SELECT id, quantity
            FROM cart_items
            WHERE cart_id = ? AND product_id = ?
            """,
            (cart_id, payload.product_id),
        ).fetchone()

        if existing:
            new_qty = existing["quantity"] + payload.quantity
            conn.execute(
                """
                UPDATE cart_items
                SET quantity = ?, unit_price = ?
                WHERE id = ?
                """,
                (new_qty, float(product["price"]), existing["id"]),
            )
        else:
            conn.execute(
                """
                INSERT INTO cart_items (cart_id, product_id, quantity, unit_price)
                VALUES (?, ?, ?, ?)
                """,
                (
                    cart_id,
                    product["id"],
                    payload.quantity,
                    float(product["price"]),
                ),
            )

        conn.commit()

        summary = _build_cart_summary(conn, cart_id)

    return {
        "cart_id": summary["cart_id"],
        "user_id": payload.user_id,
        "items": summary["items"],
        "total": summary["total"],
    }


@app.get("/carts/summary")
def api_cart_summary(user_id: int):
    with get_connection() as conn:
        cart_id = _get_open_cart_id(conn, user_id)
        if cart_id is None:
            return {
                "cart_id": None,
                "user_id": user_id,
                "items": [],
                "total": 0.0,
            }

        summary = _build_cart_summary(conn, cart_id)

    return {
        "cart_id": summary["cart_id"],
        "user_id": user_id,
        "items": summary["items"],
        "total": summary["total"],
    }


@app.post("/checkout/from_agent")
def api_checkout_from_agent(payload: CheckoutFromAgentRequest):
    with get_connection() as conn:
        cart_id = _get_open_cart_id(conn, payload.user_id)
        if cart_id is None:
            raise HTTPException(status_code=400, detail="No hay carrito abierto")

        summary = _build_cart_summary(conn, cart_id)
        if not summary["items"]:
            raise HTTPException(status_code=400, detail="El carrito está vacío")

        total = summary["total"]

        # Crear orden
        cur = conn.execute(
            """
            INSERT INTO orders (user_id, cart_id, total, payment_status)
            VALUES (?, ?, ?, ?)
            """,
            (payload.user_id, cart_id, total, "pending"),
        )
        order_id = cur.lastrowid

        # Cambiar estado del carrito
        conn.execute(
            "UPDATE carts SET status = 'checked_out' WHERE id = ?",
            (cart_id,),
        )

        # Buscar datos del usuario
        user_row = conn.execute(
            "SELECT name, email FROM users WHERE id = ?",
            (payload.user_id,),
        ).fetchone()

        user_name = user_row["name"] if user_row else "Cliente"
        email = user_row["email"] or payload.email if user_row else payload.email

        # Preparar items para el checkout (formato que espera tu script del checkout)
        items_for_payload = [
            {
                "product_id": it["product_id"],
                "name": it["product_name"],
                "quantity": it["quantity"],
                "unit_price": it["unit_price"],
                "line_total": it["line_total"],
            }
            for it in summary["items"]
        ]

        items_encoded = base64.urlsafe_b64encode(
            json.dumps(items_for_payload).encode("utf-8")
        ).decode("utf-8")

        payment_url = (
            f"{CHECKOUT_BASE_URL}"
            f"?user_id={quote_plus(str(payload.user_id))}"
            f"&name={quote_plus(user_name)}"
            f"&email={quote_plus(email)}"
            f"&amount={total:.2f}"
            f"&items={items_encoded}"
        )

        conn.commit()

    return {
        "order_id": order_id,
        "user_id": payload.user_id,
        "total": total,
        "payment_url": payment_url,
    }
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "retail_agent"))

import os
import json

os.environ["BACKOFFICE_BASE_URL"] = "http://localhost:8000"

from agent_tools_backoffice import (
    create_user,
    search_products,
    add_product_to_cart,
    get_cart_summary,
    clear_cart,
)

def pp(x):
    print(json.dumps(x, indent=2, ensure_ascii=False))

def main():
    # 1) Crear/usar usuario demo
    u = create_user(name="Demo User", email="demo.user@example.com", phone="+5491100000000")
    pp(u)

    user_id = u.get("user", {}).get("id")
    if not user_id:
        raise RuntimeError("No pude obtener user_id")

    # 2) Buscar un producto real (ej: cerveza)
    p = search_products(query="cerveza")
    pp(p)

    if p.get("status") != "success" or not p.get("items"):
        raise RuntimeError("No encontré productos con query 'cerveza'")

    product_id = p["items"][0]["id"]
    print("Usando product_id:", product_id)

    # 3) Reset carrito
    pp(clear_cart(user_id))

    # 4) Agregar 1 unidad
    pp(add_product_to_cart(user_id=user_id, product_id=product_id, quantity=1))

    # 5) Ver resumen
    pp(get_cart_summary(user_id))

    # 6) Probar stock insuficiente (debería fallar)
    pp(add_product_to_cart(user_id=user_id, product_id=product_id, quantity=999))

if __name__ == "__main__":
    main()

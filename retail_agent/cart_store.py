"""
cart_store.py
Manejo de carritos en memoria por usuario.
"""

from typing import Dict, List

# user_id -> lista de items {product_id, quantity}
CARTS: Dict[str, List[Dict]] = {}


def add_item_to_cart(user_id: str, product_id: str, quantity: int) -> Dict:
    """
    Agrega un item al carrito de un usuario.
    Si el item ya existe, acumula la cantidad.
    """
    if quantity <= 0:
        return {
            "status": "error",
            "error_message": "La cantidad debe ser mayor a 0."
        }

    cart = CARTS.get(user_id, [])

    # Buscamos si ya existe el producto
    for item in cart:
        if item["product_id"] == product_id:
            item["quantity"] += quantity
            break
    else:
        cart.append({"product_id": product_id, "quantity": quantity})

    CARTS[user_id] = cart

    return {
        "status": "success",
        "cart": cart,
    }


def get_cart_for_user(user_id: str) -> Dict:
    """
    Devuelve el carrito actual del usuario.
    """
    cart = CARTS.get(user_id, [])
    return {
        "status": "success",
        "cart": cart,
    }


def clear_cart_for_user(user_id: str) -> None:
    """
    Limpia el carrito del usuario (por ejemplo luego del checkout).
    """
    if user_id in CARTS:
        del CARTS[user_id]

"""
data.py
Base de datos de prueba en memoria para el agente de retail.
"""

from typing import List, Dict, Optional


# Usuarios de prueba
USERS: List[Dict] = [
    {
        "id": "u001",
        "name": "Sergio",
        "email": "sergio@example.com",
        "phone": "+5491111111111",
        "segment": "frecuente",
    },
    {
        "id": "u002",
        "name": "Pamela",
        "email": "pamela@example.com",
        "phone": "+5491122222222",
        "segment": "ocasional",
    },
]


# Catálogo de productos de prueba
PRODUCTS: List[Dict] = [
    {
        "id": "p001",
        "name": "Leche descremada sin lactosa 1L",
        "category": "lacteos",
        "price": 2500.0,
        "is_offer": True,
        "description": "Leche descremada sin lactosa, ideal para intolerancias.",
        "stock": 100,
    },
    {
        "id": "p002",
        "name": "Pan de molde sin TACC",
        "category": "panaderia",
        "price": 3200.0,
        "is_offer": False,
        "description": "Pan de molde apto celíacos, ideal para sandwiches.",
        "stock": 80,
    },
    {
        "id": "p003",
        "name": "Gaseosa cola 2.25L",
        "category": "bebidas",
        "price": 2100.0,
        "is_offer": True,
        "description": "Gaseosa sabor cola formato familiar.",
        "stock": 200,
    },
    {
        "id": "p004",
        "name": "Agua mineral sin gas 1.5L",
        "category": "bebidas",
        "price": 900.0,
        "is_offer": False,
        "description": "Agua mineral sin gas.",
        "stock": 300,
    },
    {
        "id": "p005",
        "name": "Galletitas de arroz integrales",
        "category": "snacks",
        "price": 1500.0,
        "is_offer": False,
        "description": "Galletitas de arroz integrales bajas en sodio.",
        "stock": 120,
    },
]


def _normalize(s: str) -> str:
    return s.lower().strip()


def find_user_by_email_or_phone(email: Optional[str], phone: Optional[str]) -> Optional[Dict]:
    """
    Busca un usuario por email o teléfono en la base de prueba.
    """
    email_norm = _normalize(email) if email else None
    phone_norm = phone.strip() if phone else None  # phone puede venir con +549...

    for u in USERS:
        if email_norm and _normalize(u["email"]) == email_norm:
            return u
        if phone_norm and u["phone"] == phone_norm:
            return u
    return None


def create_user(name: str, email: str, phone: str) -> Dict:
    """
    Crea un usuario nuevo en la base de prueba.
    IMPORTANTE: esto es solo en memoria, se pierde al reiniciar el proceso.
    """
    new_id = f"u{len(USERS) + 1:03d}"
    user = {
        "id": new_id,
        "name": name,
        "email": email,
        "phone": phone,
        "segment": "nuevo",
    }
    USERS.append(user)
    return user


def search_products_in_catalog(query: str, category: Optional[str] = None) -> List[Dict]:
    """
    Busca productos en el catálogo de prueba de manera más flexible:
    - Soporta sinónimos simples de categoría (ej: panificados -> panaderia)
    - Tokeniza el query ("pan lactal" -> "pan", "lactal")
    - Asigna un score a cada producto según coincidencias en nombre, desc y categoría
    """
    q = _normalize(query)
    cat = _normalize(category) if category else None

    # Sinónimos básicos de categoría / query
    CATEGORY_SYNONYMS = {
        "panificados": "panaderia",
        "panificado": "panaderia",
        "pan lactal": "panaderia",
    }

    # Si la categoría matchea un sinónimo, la convertimos
    if cat in CATEGORY_SYNONYMS:
        cat = CATEGORY_SYNONYMS[cat]

    # Si el query completo matchea un sinónimo, lo tratamos como categoría + query genérico
    if q in CATEGORY_SYNONYMS:
        cat = CATEGORY_SYNONYMS[q]
        q = "pan"  # query genérico más amplio

    # Tokenizamos el query para tolerar frases largas
    tokens = [t for t in q.split() if t]

    def score_product(p: Dict) -> int:
        score = 0
        name = _normalize(p["name"])
        desc = _normalize(p.get("description", ""))
        pcat = _normalize(p["category"])

        # Bonus si coincide categoría explícita
        if cat and pcat == cat:
            score += 3

        # Score por tokens en nombre, descripción y categoría
        for t in tokens:
            if t in name:
                score += 4  # nombre pesa más
            if t in desc:
                score += 2
            if t in pcat:
                score += 1

        return score

    scored: List[tuple[int, Dict]] = []
    for p in PRODUCTS:
        s = score_product(p)
        if s > 0:
            scored.append((s, p))

    # Ordenamos por score descendente
    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for (s, p) in scored]



def get_product_by_id(product_id: str) -> Optional[Dict]:
    """
    Devuelve un producto por id, o None si no existe.
    """
    for p in PRODUCTS:
        if p["id"] == product_id:
            return p
    return None

def get_user_by_id(user_id: str) -> Optional[Dict]:
    """
    Devuelve un usuario por id, o None si no existe.
    """
    for u in USERS:
        if u["id"] == user_id:
            return u
    return None
"""
Script para cargar datos de prueba en la DB.
Ejecutar después de cada deploy a Cloud Run.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "retail.db"

def seed_demo_data():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Verificar si ya hay datos
    count = cur.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count > 0:
        print(f"Ya existen {count} usuarios. Saltando seed.")
        conn.close()
        return
    
    print("Cargando datos de demo...")
    
    # Usuarios de prueba
    users = [
        ("Sergio Test", "sergio@yoplabs.com", "+5491160149123", "recurrente"),
        ("Maria Cliente", "maria@example.com", "+5491160149124", "nuevo"),
        ("Juan Comprador", "juan@example.com", "+5491160149125", "premium"),
    ]
    
    for name, email, phone, segment in users:
        try:
            cur.execute(
                "INSERT INTO users (name, email, phone, segment) VALUES (?, ?, ?, ?)",
                (name, email, phone, segment)
            )
        except sqlite3.IntegrityError:
            pass
    
    # Productos de prueba
    products = [
        ("P001", "Leche entera 1L", "Lácteos", "Leche entera pasteurizada", 1200.0, False, 150),
        ("P041", "Papel higiénico doble hoja (4 rollos)", "Limpieza", "Papel higiénico suave", 2500.0, True, 80),
        ("P092", "Tapa Para Empanadas Horno 12 u.", "Almacén", "Tapas para empanadas", 1500.0, True, 100),
        ("P050", "Mayonesa clásica pote 250g", "Almacén", "Mayonesa cremosa", 2000.0, False, 120),
    ]
    
    for sku, name, cat, desc, price, offer, stock in products:
        try:
            cur.execute(
                "INSERT INTO products (sku, name, category, description, price, is_offer, stock) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (sku, name, cat, desc, price, 1 if offer else 0, stock)
            )
        except sqlite3.IntegrityError:
            pass
    
    conn.commit()
    conn.close()
    print("✅ Datos de demo cargados exitosamente")

if __name__ == "__main__":
    seed_demo_data()

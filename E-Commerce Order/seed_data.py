"""
Run this once to (re)create ecommerce.db with mock products and orders.
    python seed_data.py
"""
import sqlite3
import os

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ecommerce.db")


def seed():
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE products (
            sku TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            stock_qty INTEGER NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE orders (
            order_id TEXT PRIMARY KEY,
            customer_name TEXT NOT NULL,
            sku TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            status TEXT NOT NULL,
            order_date TEXT NOT NULL,
            return_status TEXT DEFAULT NULL,
            FOREIGN KEY (sku) REFERENCES products (sku)
        )
    """)

    products = [
        ("SKU-1001", "Wireless Mouse", 19.99, 42),
        ("SKU-1002", "Mechanical Keyboard", 79.99, 0),
        ("SKU-1003", "USB-C Hub", 24.50, 15),
        ("SKU-1004", "27in Monitor", 219.00, 5),
        ("SKU-1005", "Laptop Stand", 34.99, 30),
    ]
    cur.executemany(
        "INSERT INTO products (sku, name, price, stock_qty) VALUES (?, ?, ?, ?)",
        products,
    )


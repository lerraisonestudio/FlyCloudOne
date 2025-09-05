import sqlite3
from werkzeug.security import generate_password_hash

# Configuración del admin
ADMIN_USERNAME = "admin"
ADMIN_EMAIL = "admin@flycloudone.com"
ADMIN_PASSWORD = "1234"  # cámbialo después de la primera vez por seguridad

def create_admin():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    # Asegurar que la tabla tenga username (tu código de app.py lo usa)
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_verified INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Verificar si ya existe un admin
    c.execute("SELECT id FROM users WHERE email = ?", (ADMIN_EMAIL,))
    if c.fetchone():
        print("⚠️ El admin ya existe, no se creó otro.")
        conn.close()
        return

    # Insertar admin
    password_hash = generate_password_hash(ADMIN_PASSWORD)
    c.execute(
        "INSERT INTO users (username, email, password_hash, is_verified) VALUES (?, ?, ?, ?)",
        (ADMIN_USERNAME, ADMIN_EMAIL, password_hash, 1)
    )
    conn.commit()
    conn.close()
    print("✅ Usuario admin creado con éxito.")
    print(f"   Usuario: {ADMIN_USERNAME}")
    print(f"   Email: {ADMIN_EMAIL}")
    print(f"   Contraseña: {ADMIN_PASSWORD}")

if __name__ == "__main__":
    create_admin()

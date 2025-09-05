import sqlite3

# Conectar o crear la base de datos
conn = sqlite3.connect("database.db")
cursor = conn.cursor()

# Crear tabla users si no existe
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL
)
""")

conn.commit()
conn.close()

print("Base de datos inicializada ✅")

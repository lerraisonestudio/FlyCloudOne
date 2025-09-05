# export_users.py
import sqlite3

def export_users():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # Ajustado a tus columnas actuales
    cursor.execute("SELECT id, username, email, created_at FROM users")
    users = cursor.fetchall()

    with open("usuarios_exportados.txt", "w", encoding="utf-8") as f:
        f.write("📋 Lista de usuarios registrados\n\n")
        for user in users:
            f.write(f"ID: {user[0]}\n")
            f.write(f"Username: {user[1]}\n")
            f.write(f"Email: {user[2]}\n")
            f.write(f"Creado: {user[3]}\n")
            f.write("-" * 40 + "\n")

    conn.close()
    print("✅ Usuarios exportados a 'usuarios_exportados.txt'")

if __name__ == "__main__":
    export_users()

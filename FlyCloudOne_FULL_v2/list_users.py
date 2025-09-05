import sqlite3

def list_users():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    # Intentar leer usuarios
    try:
        c.execute("SELECT id, username, email, is_verified, created_at FROM users")
        rows = c.fetchall()

        if not rows:
            print("⚠️ No hay usuarios en la base de datos.")
        else:
            print("📋 Lista de usuarios registrados:\n")
            for row in rows:
                print(f"ID: {row[0]}")
                print(f"Username: {row[1]}")
                print(f"Email: {row[2]}")
                print(f"Verificado: {'Sí' if row[3] else 'No'}")
                print(f"Creado: {row[4]}")
                print("-" * 40)

    except sqlite3.OperationalError as e:
        print("⚠️ Error al leer usuarios:", e)

    conn.close()

if __name__ == "__main__":
    list_users()

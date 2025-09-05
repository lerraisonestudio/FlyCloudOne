import cloudinary
import cloudinary.uploader
import os
import sqlite3
from functools import wraps
from flask import Flask, session, redirect, request, render_template, flash, url_for, send_from_directory
from flask_mail import Mail
from config import Config
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# 🔹 Cargar variables desde .env
load_dotenv()
# Cloudinary se configura automáticamente desde CLOUDINARY_URL; forzamos HTTPS
cloudinary.config(secure=True)

app = Flask(__name__)
app.config.from_object(Config)
mail = Mail(app)

# --------- Sesión / rutas ----------
app.secret_key = os.getenv("SECRET_KEY", "supersecreto123")

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

CATEGORIES = {
    "imagenes": ["png", "jpg", "jpeg", "gif", "webp"],
    "musica": ["mp3", "wav", "ogg"],
    "documentos": ["pdf", "docx", "txt", "xlsx", "pptx"],
    "contactos": ["vcf", "csv"],
    "correos": ["eml", "msg"],
    "videos": ["mp4", "avi", "mov", "mkv"],
}
for cat in CATEGORIES:
    os.makedirs(os.path.join(UPLOAD_FOLDER, cat), exist_ok=True)

# ========= DB: SQLite local o PostgreSQL en producción =========
DATABASE_URL = os.getenv("DATABASE_URL")  # Railway la pone automáticamente al añadir Postgres
USING_PG = bool(DATABASE_URL)

def get_conn():
    if USING_PG:
        import psycopg2
        # Railway normalmente no exige SSL local; si lo pide, deja sslmode=require
        return psycopg2.connect(DATABASE_URL)
    else:
        return sqlite3.connect("database.db")

def adapt_q(q: str) -> str:
    """Convierte placeholders de SQLite (?) a PostgreSQL (%s) si hace falta."""
    if USING_PG:
        return q.replace("?", "%s")
    return q

def run(q: str, params=(), *, fetchone=False, fetchall=False, commit=False):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(adapt_q(q), params)
    data = None
    if fetchone:
        data = cur.fetchone()
    elif fetchall:
        data = cur.fetchall()
    if commit:
        conn.commit()
    cur.close()
    conn.close()
    return data

def ensure_schema():
    if USING_PG:
        # Esquema para PostgreSQL
        run("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_verified BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """, commit=True)
    else:
        # Esquema y migraciones básicas para SQLite
        conn = sqlite3.connect("database.db")
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT,
                is_verified INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Migración mínima (por si vienes de versiones previas)
        cols = {row[1] for row in c.execute("PRAGMA table_info(users)").fetchall()}
        if "username" not in cols:
            c.execute("ALTER TABLE users ADD COLUMN username TEXT")
        if "password_hash" not in cols:
            c.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
            if "password" in cols:
                c.execute("UPDATE users SET password_hash = password WHERE password_hash IS NULL")
        conn.commit()
        conn.close()

ensure_schema()

# --------- Helpers de auth ----------
def allowed_file(filename, category):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in CATEGORIES.get(category, [])

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return decorated

@app.context_processor
def inject_auth_urls():
    return {
        "is_logged_in": bool(session.get("user_id")),
        "login_url": url_for("login"),
        "logout_url": url_for("logout"),
    }

# ------------------ Auth ------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username_or_email = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        row = run(
            "SELECT id, password_hash FROM users WHERE email = ? OR username = ?",
            (username_or_email.lower(), username_or_email),
            fetchone=True
        )
        if row and check_password_hash(row[1], password):
            session['user_id'] = row[0]
            next_url = request.args.get('next') or url_for('index')
            return redirect(next_url)

        flash("Usuario o contraseña incorrectos")
        return redirect(url_for('login'))

    return render_template('login.html')

@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not username or not email or not password or not confirm_password:
            flash("Debes completar todos los campos")
            return redirect(url_for("register"))
        if password != confirm_password:
            flash("Las contraseñas no coinciden")
            return redirect(url_for("register"))

        exists = run("SELECT id FROM users WHERE lower(email) = lower(?)", (email,), fetchone=True)
        if exists:
            flash("Este correo ya está registrado")
            return redirect(url_for("register"))

        password_hash = generate_password_hash(password)
        run(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (username, email, password_hash),
            commit=True
        )

        flash("Registro exitoso, ya puedes iniciar sesión")
        return redirect(url_for("login"))

    return render_template("register.html")

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')

        # Buscar usuario por username
        row = run("SELECT id, password_hash FROM users WHERE username = ?", (username,), fetchone=True)
        if not row:
            flash('Usuario no encontrado.', 'error')
            return redirect(url_for('reset_password'))

        user_id, pw_hash = row[0], row[1]
        if not check_password_hash(pw_hash, current_password):
            flash('La contraseña actual no es correcta.', 'error')
            return redirect(url_for('reset_password'))

        new_hash = generate_password_hash(new_password)
        run("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user_id), commit=True)

        flash('Contraseña actualizada con éxito. Inicia sesión de nuevo.', 'success')
        return redirect(url_for('login'))

    return render_template('reset_password.html')

# ------------------ Archivos ------------------
@app.route("/upload/<category>", methods=["POST"])
@login_required
def upload(category):
    if category not in CATEGORIES:
        return redirect(url_for("index"))
    if "file" not in request.files:
        return redirect(url_for("index"))

    file = request.files["file"]
    if not file or file.filename == "":
        return redirect(url_for("index"))
    if not allowed_file(file.filename, category):
        return redirect(url_for("index"))

    # Si hay Postgres (Railway), sube a Cloudinary y guarda en DB
    if USING_PG:
        # Carpeta por categoría y usuario para mantener ordenado
        folder = f"{category}/{session['user_id']}"
        result = cloudinary.uploader.upload(file, folder=folder)
        public_id = result["public_id"]
        file_url = result["secure_url"]
        file_name = secure_filename(file.filename)

        run(
            "INSERT INTO files (user_id, category, file_name, public_id, url) VALUES (?, ?, ?, ?, ?)",
            (session["user_id"], category, file_name, public_id, file_url),
            commit=True
        )
        return redirect(url_for("index") + f"#{category}")

    # Si estás local sin DB, usa la carpeta uploads como antes
    filename = secure_filename(file.filename)
    save_path = os.path.join(app.config["UPLOAD_FOLDER"], category, filename)
    file.save(save_path)
    return redirect(url_for("index") + f"#{category}")

@app.route("/download/<category>/<filename>")
@login_required
def download(category, filename):
    if category not in CATEGORIES:
        return redirect(url_for("index"))

    if USING_PG:
        row = run(
            "SELECT url FROM files WHERE user_id = ? AND category = ? AND file_name = ?",
            (session["user_id"], category, filename),
            fetchone=True
        )
        if row:
            # Redirige al URL (Cloudinary sirve el archivo)
            return redirect(row[0])
        return redirect(url_for("index") + f"#{category}")

    # Local (sin DB)
    return send_from_directory(os.path.join(app.config["UPLOAD_FOLDER"], category), filename, as_attachment=True)

@app.route("/preview/<category>/<path:filename>")
@login_required
def preview(category, filename):
    if category not in CATEGORIES:
        return redirect(url_for("index"))

    if USING_PG:
        row = run(
            "SELECT url FROM files WHERE user_id = ? AND category = ? AND file_name = ?",
            (session["user_id"], category, filename),
            fetchone=True
        )
        if row:
            # Redirige al archivo en Cloudinary para verlo en el navegador
            return redirect(row[0])
        return redirect(url_for("index") + f"#{category}")

    # Local (sin DB)
    return send_from_directory(os.path.join(app.config["UPLOAD_FOLDER"], category), filename, as_attachment=False)

@app.route("/uploads/<category>/<path:filename>")
@login_required
def uploaded_file(category, filename):
    if category not in CATEGORIES:
        return redirect(url_for("index"))
    return send_from_directory(os.path.join(app.config["UPLOAD_FOLDER"], category), filename)

@app.route("/delete/<category>/<filename>")
@login_required
def delete(category, filename):
    if category not in CATEGORIES:
        return redirect(url_for("index"))
    file_path = os.path.join(app.config["UPLOAD_FOLDER"], category, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
    return redirect(url_for("index") + f"#{category}")

# ------------------ Index ------------------
@app.route("/")
@login_required
def index():
    files = {}
    for cat in CATEGORIES:
        folder = os.path.join(app.config["UPLOAD_FOLDER"], cat)
        try:
            files[cat] = sorted([f for f in os.listdir(folder) if not f.startswith(".")])
        except FileNotFoundError:
            files[cat] = []
    return render_template("index.html", **files)

if __name__ == "__main__":
    # Local solamente. En Railway arranca con gunicorn via Procfile.
    app.run(host="0.0.0.0", port=5000, debug=True)


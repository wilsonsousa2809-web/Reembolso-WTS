from flask import Flask, render_template, request, redirect, session, url_for, flash, send_from_directory
import sqlite3, os
from werkzeug.utils import secure_filename

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = "segredo_seguro_produto"

DB_NAME = "database.db"
UPLOAD_FOLDER = "uploads"
ALLOWED_EXT = {"png","jpg","jpeg","pdf"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return "." in filename and filename.rsplit(".",1)[1].lower() in ALLOWED_EXT

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS usuarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT,
                    email TEXT UNIQUE,
                    senha TEXT,
                    admin INTEGER DEFAULT 0
                )""")
    c.execute("""CREATE TABLE IF NOT EXISTS solicitacoes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    usuario_id INTEGER,
                    descricao TEXT,
                    valor REAL,
                    data TEXT,
                    categoria TEXT,
                    observacoes TEXT,
                    comprovante TEXT,
                    status TEXT DEFAULT 'Pendente',
                    FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
                )""")
    # create default admin if not exists
    c.execute("SELECT id FROM usuarios WHERE email=?", ("admin@reembolso.com",))
    if not c.fetchone():
        c.execute("INSERT INTO usuarios (nome, email, senha, admin) VALUES (?, ?, ?, ?)",
                  ("Admin", "admin@reembolso.com", "admin", 1))
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def home():
    if "usuario" in session:
        if session.get("admin"):
            return redirect(url_for("painel_admin"))
        return redirect(url_for("dashboard"))
    return render_template("login.html")

@app.route('/login', methods=["POST"])
def login():
    email = request.form.get("email")
    senha = request.form.get("senha")
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM usuarios WHERE email=? AND senha=?", (email, senha))
    user = c.fetchone()
    conn.close()
    if user:
        session["usuario"] = user[1]
        session["user_id"] = user[0]
        session["admin"] = bool(user[4])
        if session["admin"]:
            return redirect(url_for("painel_admin"))
        return redirect(url_for("dashboard"))
    flash("Usuário ou senha inválidos.")
    return redirect(url_for("home"))

@app.route('/registrar', methods=["GET","POST"])
def registrar():
    if request.method == "POST":
        nome = request.form.get("nome")
        email = request.form.get("email")
        senha = request.form.get("senha")
        try:
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("INSERT INTO usuarios (nome, email, senha) VALUES (?, ?, ?)", (nome, email, senha))
            conn.commit()
            conn.close()
            flash("Conta criada com sucesso! Faça login.")
            return redirect(url_for("home"))
        except Exception as e:
            flash("Erro ao criar conta — email pode já estar cadastrado.")
            return redirect(url_for("registrar"))
    return render_template("registro.html")

@app.route('/dashboard')
def dashboard():
    if "usuario" not in session or session.get("admin"):
        return redirect(url_for("home"))
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM solicitacoes WHERE usuario_id=?", (session["user_id"],))
    solicitacoes = c.fetchall()
    conn.close()
    return render_template("dashboard.html", solicitacoes=solicitacoes, usuario=session["usuario"])

@app.route('/nova', methods=["GET", "POST"])
def nova_solicitacao():
    if "usuario" not in session or session.get("admin"):
        return redirect(url_for("home"))
    if request.method == "POST":
        descricao = request.form.get("descricao")
        valor = request.form.get("valor")
        data = request.form.get("data")
        categoria = request.form.get("categoria")
        obs = request.form.get("obs")
        arquivo = request.files.get("comprovante")
        nome_arquivo = None
        if arquivo and arquivo.filename and allowed_file(arquivo.filename):
            filename = secure_filename(arquivo.filename)
            nome_arquivo = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            arquivo.save(nome_arquivo)
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("""INSERT INTO solicitacoes
                     (usuario_id, descricao, valor, data, categoria, observacoes, comprovante)
                     VALUES (?, ?, ?, ?, ?, ?, ?)""",
                  (session["user_id"], descricao, valor, data, categoria, obs, nome_arquivo))
        conn.commit()
        conn.close()
        flash("Solicitação enviada com sucesso!")
        return redirect(url_for("dashboard"))
    return render_template("nova_solicitacao.html")

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

@app.route('/admin')
def painel_admin():
    if "usuario" not in session or not session.get("admin"):
        return redirect(url_for("home"))
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT s.id, u.nome, s.descricao, s.valor, s.data, s.categoria, s.status FROM solicitacoes s JOIN usuarios u ON s.usuario_id = u.id")
    solicitacoes = c.fetchall()
    conn.close()
    return render_template("admin.html", solicitacoes=solicitacoes, usuario=session["usuario"])

@app.route('/atualizar_status/<int:id>/<status>')
def atualizar_status(id, status):
    if "usuario" not in session or not session.get("admin"):
        return redirect(url_for("home"))
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE solicitacoes SET status=? WHERE id=?", (status, id))
    conn.commit()
    conn.close()
    flash("Status atualizado.")
    return redirect(url_for("painel_admin"))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for("home"))

if __name__ == "__main__":
    # For local development; production uses Procfile + gunicorn
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)

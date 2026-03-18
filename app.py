import os
import requests
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "incabit-dev-key")

SITE = {
    "brand": "incaB1T",
    "tagline": "Detecta objetos, comportamientos, anticipa acciones",
    "email": "cesar@incabit.com",
    "phone": "+51 943002381",
    "whatsapp": "51943002381"
}

# =========================
# CONFIG POSTGRESQL
# =========================
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:DBadmin28$@localhost:5232/incabit_db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# =========================
# CONFIG UPLOADS
# =========================
UPLOAD_FOLDER = os.path.join("static", "uploads", "emergencias")
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # 8 MB


# =========================
# MODELO
# =========================
class Incidente(db.Model):
    __tablename__ = "incidentes"

    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(30), unique=True, nullable=False)
    tipo_reporte = db.Column(db.String(50), nullable=False)
    descripcion = db.Column(db.Text, nullable=False)
    latitud = db.Column(db.String(30), nullable=False)
    longitud = db.Column(db.String(30), nullable=False)
    direccion_texto = db.Column(db.String(255), nullable=True)
    ruta_imagen = db.Column(db.String(255), nullable=False)
    estado = db.Column(db.String(30), nullable=False, default="nuevo")
    fecha_registro = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


@app.context_processor
def inject_site():
    return dict(site=SITE)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def generar_codigo_incidente():
    return f"INC-{datetime.now().strftime('%Y%m%d-%H%M%S')}"


def obtener_direccion_textual(latitud, longitud):
    """
    Obtiene una dirección textual aproximada a partir de lat/lon
    usando Nominatim (OpenStreetMap).
    """
    url = "https://nominatim.openstreetmap.org/reverse"
    params = {
        "lat": latitud,
        "lon": longitud,
        "format": "jsonv2",
        "addressdetails": 1
    }
    headers = {
        "User-Agent": "incabit-emergencias/1.0 (cesar@incabit.com)"
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        # display_name suele traer la dirección más completa
        direccion = data.get("display_name", "").strip()
        return direccion if direccion else None

    except Exception:
        return None


@app.route("/")
def home():
    return render_template("index.html", page_title="Inicio")


@app.route("/aprendizaje")
def aprendizaje():
    return render_template("aprendizaje.html", page_title="Aprendizaje")


@app.route("/plataforma")
def plataforma():
    return render_template("plataforma.html", page_title="Plataforma")


@app.route("/emergencia")
def emergencia():
    return render_template("emergencia.html", page_title="Emergencia")


@app.route("/emergencia/reportar", methods=["GET", "POST"])
def emergencia_reportar():
    if request.method == "POST":
        tipo_reporte = request.form.get("tipo_reporte", "").strip()
        descripcion = request.form.get("descripcion", "").strip()
        latitud = request.form.get("latitud", "").strip()
        longitud = request.form.get("longitud", "").strip()
        direccion_texto = obtener_direccion_textual(latitud, longitud)
        evidencia = request.files.get("evidencia")

        errores = []

        if not tipo_reporte:
            errores.append("Debes seleccionar el tipo de reporte.")

        if not descripcion:
            errores.append("Debes ingresar una descripción del incidente.")

        if not latitud or not longitud:
            errores.append("No se pudo obtener la ubicación. Activa el GPS del celular.")

        if not evidencia or not evidencia.filename:
            errores.append("Debes adjuntar una imagen tomada o cargada desde el celular.")

        if evidencia and evidencia.filename and not allowed_file(evidencia.filename):
            errores.append("La imagen debe ser JPG, JPEG, PNG o WEBP.")

        if errores:
            for error in errores:
                flash(error, "error")
            return render_template("emergencia_reportar.html", page_title="Reportar Emergencia")

        codigo_incidente = generar_codigo_incidente()

        extension = evidencia.filename.rsplit(".", 1)[1].lower()
        nombre_archivo = secure_filename(f"{codigo_incidente}.{extension}")
        ruta_archivo = os.path.join(app.config["UPLOAD_FOLDER"], nombre_archivo)
        evidencia.save(ruta_archivo)

        ruta_relativa = f"uploads/emergencias/{nombre_archivo}"

        nuevo_incidente = Incidente(
            codigo=codigo_incidente,
            tipo_reporte=tipo_reporte,
            descripcion=descripcion,
            latitud=latitud,
            longitud=longitud,
            direccion_texto=direccion_texto,
            ruta_imagen=ruta_relativa,
            estado="nuevo"
        )

        try:
            db.session.add(nuevo_incidente)
            db.session.commit()
            flash("Emergencia registrada correctamente.", "success")
            return redirect(url_for("emergencia_estado", codigo=codigo_incidente))
        except Exception as e:
            db.session.rollback()
            flash(f"Error al guardar en la base de datos: {str(e)}", "error")
            return render_template("emergencia_reportar.html", page_title="Reportar Emergencia")

    return render_template("emergencia_reportar.html", page_title="Reportar Emergencia")


@app.route("/emergencia/estado/<codigo>")
def emergencia_estado(codigo):
    incidente = Incidente.query.filter_by(codigo=codigo).first_or_404()
    return render_template(
        "emergencia_estado.html",
        page_title="Estado de Emergencia",
        incidente=incidente
    )


@app.route("/soluciones")
def soluciones():
    return render_template("soluciones.html", page_title="Soluciones")


@app.route("/demo")
def demo():
    return render_template("demo.html", page_title="Demo")


@app.route("/contacto")
def contacto():
    return render_template("contacto.html", page_title="Contacto")


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
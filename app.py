import os
import cv2
import base64
import requests
import numpy as np

from datetime import datetime, timedelta
from ultralytics import YOLO
from werkzeug.utils import secure_filename
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify
)
from flask_sqlalchemy import SQLAlchemy


app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "incabit-dev-key")


SITE = {
    "brand": "incaB1T",
    "tagline": "Seguridad en Lima con Inteligencia Artificial",
    "email": "cesar@incabit.com",
    "phone": "+51 943002381",
    "whatsapp": "51943002381"
}


# =========================================================
# CONFIGURACIÓN POSTGRESQL
# =========================================================
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:DBadmin28$@localhost:5432/incabit_db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# =========================================================
# CONFIGURACIÓN UPLOADS
# =========================================================
UPLOAD_FOLDER = os.path.join("static", "uploads", "emergencias")
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # 8 MB


# =========================================================
# CONFIGURACIÓN YOLO
# =========================================================
YOLO_MODEL_NAME = "yolo11n.pt"
YOLO_CONFIDENCE = 0.5

# Clases COCO seleccionadas:
# 0 person, 2 car, 3 motorcycle, 5 bus, 7 truck
YOLO_CLASSES = [0, 2, 3, 5, 7]

yolo_model = None


# =========================================================
# MODELOS
# =========================================================
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


class TransmisionActiva(db.Model):
    __tablename__ = "transmisiones_activas"

    id = db.Column(db.Integer, primary_key=True)
    estado = db.Column(db.String(20), nullable=False, default="libre")
    iniciada_en = db.Column(db.DateTime, nullable=True)
    expira_en = db.Column(db.DateTime, nullable=True)

    ip_usuario = db.Column(db.String(50), nullable=True)
    hora_exacta_inicio = db.Column(db.DateTime, nullable=True)
    hora_exacta_fin = db.Column(db.DateTime, nullable=True)
    motivo_cierre = db.Column(db.String(100), nullable=True)


# =========================================================
# CONTEXT PROCESSOR
# =========================================================
@app.context_processor
def inject_site():
    return dict(site=SITE)


# =========================================================
# HELPERS GENERALES
# =========================================================
def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def generar_codigo_incidente() -> str:
    return f"INC-{datetime.now().strftime('%Y%m%d-%H%M%S')}"


def obtener_ip_cliente() -> str:
    if request.headers.get("X-Forwarded-For"):
        return request.headers.get("X-Forwarded-For").split(",")[0].strip()
    return request.remote_addr or "desconocida"


def obtener_direccion_textual(latitud: str, longitud: str):
    """
    Reverse geocoding usando Nominatim.
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
        direccion = data.get("display_name", "").strip()
        return direccion if direccion else None
    except Exception:
        return None


# =========================================================
# HELPERS TRANSMISIÓN
# =========================================================
def obtener_o_crear_control_transmision():
    control = TransmisionActiva.query.filter_by(id=1).first()

    if not control:
        control = TransmisionActiva(
            id=1,
            estado="libre",
            iniciada_en=None,
            expira_en=None,
            ip_usuario=None,
            hora_exacta_inicio=None,
            hora_exacta_fin=None,
            motivo_cierre=None
        )
        db.session.add(control)
        db.session.commit()

    return control


def liberar_transmision_si_expirada():
    control = obtener_o_crear_control_transmision()
    ahora = datetime.utcnow()

    # si ya pasó la expiración, o si por seguridad lleva más de 15 segundos activa
    if control.estado == "activa":
        expiro_por_fecha = control.expira_en and ahora >= control.expira_en
        expiro_por_tiempo = control.iniciada_en and (ahora - control.iniciada_en).total_seconds() > 15

        if expiro_por_fecha or expiro_por_tiempo:
            control.estado = "libre"
            control.hora_exacta_fin = ahora
            control.motivo_cierre = "recuperacion_automatica"
            control.ip_usuario = None
            db.session.commit()

    return control


# =========================================================
# HELPERS YOLO
# =========================================================
def get_yolo_model():
    global yolo_model
    if yolo_model is None:
        yolo_model = YOLO(YOLO_MODEL_NAME)
    return yolo_model


def procesar_frame_yolo_desde_base64(data_url: str):
    """
    Recibe una imagen base64 (data:image/jpeg;base64,...)
    y devuelve imagen anotada + detecciones + conteo.
    """
    try:
        if "," not in data_url:
            return {"ok": False, "error": "Formato de imagen inválido"}

        _, encoded = data_url.split(",", 1)
        image_bytes = base64.b64decode(encoded)
        np_array = np.frombuffer(image_bytes, np.uint8)
        frame = cv2.imdecode(np_array, cv2.IMREAD_COLOR)

        if frame is None:
            return {"ok": False, "error": "No se pudo decodificar el frame"}

        model = get_yolo_model()

        results = model.predict(
            source=frame,
            conf=YOLO_CONFIDENCE,
            classes=YOLO_CLASSES,
            verbose=False
        )

        result = results[0]
        annotated = result.plot()

        detecciones = []
        conteo = {}

        if result.boxes is not None:
            names = result.names
            for box in result.boxes:
                cls_id = int(box.cls[0].item())
                conf = float(box.conf[0].item())

                if conf >= YOLO_CONFIDENCE:
                    clase = names[cls_id]
                    detecciones.append({
                        "clase": clase,
                        "confianza": round(conf, 3)
                    })
                    conteo[clase] = conteo.get(clase, 0) + 1

        ok, buffer = cv2.imencode(".jpg", annotated)
        if not ok:
            return {"ok": False, "error": "No se pudo codificar la imagen procesada"}

        annotated_base64 = base64.b64encode(buffer).decode("utf-8")
        annotated_data_url = f"data:image/jpeg;base64,{annotated_base64}"

        return {
            "ok": True,
            "imagen_procesada": annotated_data_url,
            "detecciones": detecciones,
            "conteo": conteo
        }

    except Exception as e:
        return {"ok": False, "error": str(e)}


# =========================================================
# RUTAS PÚBLICAS
# =========================================================
@app.route("/")
def home():
    return render_template("index.html", page_title="Inicio")


@app.route("/aprendizaje")
def aprendizaje():
    return render_template("aprendizaje.html", page_title="Aprendizaje")


@app.route("/plataforma")
def plataforma():
    return render_template("plataforma.html", page_title="Plataforma")


@app.route("/soluciones")
def soluciones():
    return render_template("soluciones.html", page_title="Soluciones")


@app.route("/demo")
def demo():
    return render_template("demo.html", page_title="Demo")


@app.route("/contacto")
def contacto():
    return render_template("contacto.html", page_title="Contacto")


# =========================================================
# RUTAS EMERGENCIA
# =========================================================
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
        evidencia = request.files.get("evidencia")

        errores = []

        if not tipo_reporte:
            errores.append("Seleccionar el tipo de reporte")

        if not descripcion:
            errores.append("Ingresar una descripción del incidente")

        if not latitud or not longitud:
            errores.append("No se pudo obtener la ubicación. Activa el GPS del celular.")

        if not evidencia or not evidencia.filename:
            errores.append("Adjuntar imagen o cargar desde el celular")

        if evidencia and evidencia.filename and not allowed_file(evidencia.filename):
            errores.append("La imagen debe ser JPG, JPEG, PNG o WEBP.")

        if errores:
            for error in errores:
                flash(error, "error")
            return render_template("emergencia_reportar.html", page_title="Reportar Emergencia")

        direccion_texto = obtener_direccion_textual(latitud, longitud)
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


@app.route("/emergencia/transmitir")
def emergencia_transmitir():
    return render_template("emergencia_transmitir.html", page_title="Transmitir Emergencia")


# =========================================================
# API TRANSMISIÓN
# =========================================================
@app.route("/api/emergencia/iniciar-transmision", methods=["POST"])
def api_iniciar_transmision():
    try:
        # print(">>> Entró a iniciar transmisión")
        control = liberar_transmision_si_expirada()
        # print(">>> Estado actual:", control.estado)

        ahora = datetime.utcnow()

        if control.estado == "activa":
            return jsonify({
                "ok": False,
                "error": "Se está realizando una transmisión en vivo, espere unos minutos"
            }), 409

        control.estado = "activa"
        control.iniciada_en = ahora
        control.expira_en = ahora + timedelta(seconds=10)
        control.ip_usuario = obtener_ip_cliente()
        control.hora_exacta_inicio = ahora
        control.hora_exacta_fin = None
        control.motivo_cierre = None

        db.session.commit()
        # print(">>> Transmisión iniciada correctamente")

        return jsonify({
            "ok": True,
            "mensaje": "Transmisión autorizada",
            "duracion_segundos": 10
        })

    except Exception as e:
        db.session.rollback()
        # print(">>> ERROR REAL EN api_iniciar_transmision:", repr(e))
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500


@app.route("/api/emergencia/finalizar-transmision", methods=["POST"])
def api_finalizar_transmision():
    try:
        control = obtener_o_crear_control_transmision()
        ahora = datetime.utcnow()

        control.estado = "libre"
        control.hora_exacta_fin = ahora
        control.motivo_cierre = "manual"
        control.ip_usuario = None

        db.session.commit()

        return jsonify({
            "ok": True,
            "mensaje": "Transmisión finalizada"
        })

    except Exception as e:
        db.session.rollback()
        # print("ERROR api_finalizar_transmision:", str(e))
        return jsonify({
            "ok": False,
            "error": f"Error al finalizar la transmisión: {str(e)}"
        }), 500


@app.route("/api/emergencia/procesar-frame", methods=["POST"])
def api_procesar_frame():
    control = liberar_transmision_si_expirada()

    if control.estado != "activa":
        return jsonify({
            "ok": False,
            "error": "No hay una transmisión activa autorizada."
        }), 403

    data = request.get_json(silent=True) or {}
    frame_data = data.get("frame")

    if not frame_data:
        return jsonify({"ok": False, "error": "No se recibió ningún frame"}), 400

    resultado = procesar_frame_yolo_desde_base64(frame_data)

    if not resultado["ok"]:
        return jsonify(resultado), 400

    return jsonify(resultado)


@app.route("/api/emergencia/estado-transmision")
def estado_transmision():
    control = liberar_transmision_si_expirada()

    return jsonify({
        "estado": control.estado,
        "iniciada_en": str(control.iniciada_en),
        "expira_en": str(control.expira_en)
    })


@app.route("/debug/transmision")
def debug_transmision():
    try:
        control = obtener_o_crear_control_transmision()
        return {
            "id": control.id,
            "estado": control.estado,
            "iniciada_en": str(control.iniciada_en),
            "expira_en": str(control.expira_en),
            "ip_usuario": control.ip_usuario,
            "hora_exacta_inicio": str(control.hora_exacta_inicio),
            "hora_exacta_fin": str(control.hora_exacta_fin),
            "motivo_cierre": control.motivo_cierre
        }
    except Exception as e:
        return {"error": str(e)}, 500


# =========================================================
# INICIO
# =========================================================
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        obtener_o_crear_control_transmision()

    app.run(
        debug=True,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000"))
    )
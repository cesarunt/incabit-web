import os
import cv2
import base64
import requests
import numpy as np
from urllib.parse import quote_plus
from datetime import datetime, timedelta
from ultralytics import YOLO
from openvino import Core
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
import cloudinary
import cloudinary.uploader
from cloudinary.utils import cloudinary_url
from flask_sqlalchemy import SQLAlchemy


app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "incabit-dev-key")

# Configuración de Cloudinary
cloudinary.config(
    cloud_name = os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key    = os.environ.get("CLOUDINARY_API_KEY"),
    api_secret = os.environ.get("CLOUDINARY_API_SECRET"),
    secure     = True,
)

SITE = {
    "brand": "incaB1T",
    "tagline": "Seguridad en Lima con Inteligencia Artificial",
    "email": "cesar@incabit.com",
    "phone": "+51 943002381"
}


# =========================================================
# CONFIGURACIÓN POSTGRESQL
# =========================================================
database_url = os.getenv("DATABASE_URL")

if database_url:
    # Producción (Render)
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
else:
    # Local
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "incabit_db")
    db_user = os.getenv("DB_USER", "postgres")
    db_password = quote_plus(os.getenv("DB_PASSWORD", "DBadmin28$"))

    app.config["SQLALCHEMY_DATABASE_URI"] = (
        f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    )

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


# =========================================================
# CONFIGURACIÓN UPLOADS
# =========================================================
UPLOAD_FOLDER = os.path.join("static", "uploads", "emergency_report")
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # 8 MB


# =========================================================
# CONFIGURACIÓN YOLO
# =========================================================
YOLO_MODEL_NAME = "yolo11n.pt"
YOLO_CONFIDENCE = 0.45

# Clases COCO seleccionadas:
# 0 person, 2 car, 3 motorcycle, 5 bus, 7 truck
YOLO_CLASSES = [0, 1, 2, 3, 5, 7, 16]

yolo_model = None

# =========================================================
# CONFIGURACIÓN TRANSMISIÓN
# =========================================================
TRANSMISSION_DURATION_SECONDS = 24
TRANSMISSION_GRACE_SECONDS = 5

# =========================================================
# CONFIGURACIÓN RUNPOD
# =========================================================
RUNPOD_URL = "https://api.runpod.ai/v2/1cicb4kg8rp3kf/runsync"
API_KEY = os.getenv("RUNPOD_API_KEY")

# =========================================================
# CONFIGURACIÓN OPENVINO (Añadir después de la config YOLO)
# =========================================================
OV_CORE = None
OV_MODEL = None

# Lista completa de objetos
COCO_CLASSES = [
    'persona', 'bicicleta', 'carro', 'moto', 'avion', 'bus', 'tren', 'camion', 'bote', 'semaforo',
    'hidrante', 'stop', 'parquimetro', 'banca', 'pajaro', 'gato', 'perro', 'caballo', 'oveja', 'vaca',
    'elefante', 'oso', 'cebra', 'jirafa', 'mochila', 'paraguas', 'cartera', 'corbata', 'maleta', 'frisbee',
    'skis', 'snowboard', 'pelota', 'cometa', 'bate', 'guante', 'skateboard', 'tabla_surf', 'raqueta', 'botella',
    'copa', 'taza', 'tenedor', 'cuchillo', 'cuchara', 'tazon', 'banana', 'manzana', 'sandwich', 'naranja',
    'brócoli', 'zanahoria', 'hot_dog', 'pizza', 'dona', 'pastel', 'silla', 'sofá', 'planta', 'cama',
    'comedor', 'baño', 'tv', 'laptop', 'mouse', 'control', 'teclado', 'celular', 'microondas', 'horno',
    'tostadora', 'fregadero', 'refrigerador', 'libro', 'reloj', 'florero', 'tijeras', 'teddy', 'secador', 'cepillo'
]
# Lista de objetos por detectar
MIS_CLASES = ['persona', 'bicicleta', 'carro', 'moto', 'bus', 'camion', 'semaforo', 'hidrante', 'stop', 'perro', 
                 'pajaro', 'gato', 'mochila', 'cartera', 'maleta', 'pelota', 'botella', 'copa', 'taza', 'tenedor', 
                 'cuchillo', 'cuchara', 'pastel', 'silla', 'sofá', 'planta', 'cama', 'comedor', 'baño', 'tv', 'laptop', 
                 'mouse', 'teclado', 'celular', 'horno', 'refrigerador', 'libro', 'reloj', 'florero']

def get_openvino_model():
    global OV_CORE, OV_MODEL
    if OV_MODEL is None:
        try:
            OV_CORE = Core()
            # La carpeta debe estar en la raíz de tu proyecto Incabit
            model_path = os.path.join(os.getcwd(), "yolo11n_openvino_model", "model.xml")
            if not os.path.exists(model_path):
                print(f"ERROR: No se encontró el modelo en {model_path}")
                return None
            net = OV_CORE.read_model(model=model_path)
            OV_MODEL = OV_CORE.compile_model(model=net, device_name="CPU")
            print("Motor OpenVINO cargado exitosamente en Incabit.")
        except Exception as e:
            print(f"Error cargando OpenVINO: {e}")
    return OV_MODEL

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

    if control.estado == "activa":
        expiro_por_fecha = control.expira_en and ahora >= control.expira_en

        expiro_por_tiempo = (
            control.iniciada_en and
            (ahora - control.iniciada_en).total_seconds() >
            (TRANSMISSION_DURATION_SECONDS + TRANSMISSION_GRACE_SECONDS)
        )

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
            imgsz=640,
            verbose=False
        )

        result = results[0]
        # annotated = result.plot()

        detecciones = []
        conteo = {}

        if result.boxes is not None:
            names = result.names
            for box in result.boxes:
                coords = box.xyxy[0].tolist() # [x1, y1, x2, y2]
                cls_id = int(box.cls[0].item())
                clase = names[cls_id]
                detecciones.append({
                    "clase": names[cls_id],
                    "confianza": round(float(box.conf[0].item()), 2),
                    "bbox": coords # <-- Sin esto, el celular no sabe dónde dibujar
                })
                conteo[clase] = conteo.get(clase, 0) + 1

        # 1. Asegúrate de que el diccionario de conteo tenga las llaves correctas
        conteo_formateado = {
            "person": conteo.get("person", 0),
            "car": conteo.get("car", 0),
            "motorcycle": conteo.get("motorcycle", 0),
            "bus": conteo.get("bus", 0),
            "truck": conteo.get("truck", 0),
            "dog": conteo.get("dog", 0)
        }

        return {
            "ok": True,
            "objects": detecciones,
            "conteo": conteo_formateado,
            "imagen_procesada": data_url
        }

    except Exception as e:
        return {"ok": False, "error": str(e)}


def procesar_y_detectar(frame_original):
    try:
        # Redimensionar para que el envío desde Lima sea ultra rápido
        frame_pequeno = cv2.resize(frame_original, (640, 480))
        _, buffer = cv2.imencode('.jpg', frame_pequeno, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        img_base64 = base64.b64encode(buffer).decode('utf-8')

        payload = {"input": {"frame": img_base64}}
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }

        response = requests.post(RUNPOD_URL, json=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            res_json = response.json()
            if res_json.get("status") == "COMPLETED":
                return res_json["output"]
            
        return None
    except Exception as e:
        print(f"Error RunPod: {e}")
        return []

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

@app.route("/transmitir")
def transmitir():
    return render_template("emergencia_transmitir.html", page_title="Transmitir")


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
        control = liberar_transmision_si_expirada()
        ahora = datetime.utcnow()

        if control.estado == "activa":
            return jsonify({
                "ok": False,
                "error": "Se está realizando una transmisión en vivo, espere unos minutos"
            }), 409

        control.estado = "activa"
        control.iniciada_en = ahora
        control.expira_en = ahora + timedelta(seconds=TRANSMISSION_DURATION_SECONDS)
        control.ip_usuario = obtener_ip_cliente()
        control.hora_exacta_inicio = ahora
        control.hora_exacta_fin = None
        control.motivo_cierre = None

        db.session.commit()

        return jsonify({
            "ok": True,
            "mensaje": "Transmisión autorizada",
            "duracion_segundos": TRANSMISSION_DURATION_SECONDS
        })

    except Exception as e:
        db.session.rollback()
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


@app.route("/api/emergencia/procesar-frame-ultralytics", methods=["POST"])
def api_procesar_frame_cpu():
    control = liberar_transmision_si_expirada()
    if control.estado != "activa":
        return jsonify({"ok": False, "error": "No hay una transmisión activa"}), 403

    data = request.get_json(silent=True) or {}
    frame_data = data.get("frame")

    # LLAMADA CORREGIDA:
    # Asegúrate de que procesar_frame_yolo_desde_base64 devuelva un DICCIONARIO, 
    # no un jsonify().
    resultado = procesar_frame_yolo_desde_base64(frame_data)

    # Si resultado ya es un diccionario, esto funcionará:
    if not resultado.get("ok"):
        return jsonify(resultado), 400

    return jsonify(resultado)


# =========================================================
# NUEVA RUTA API PARA OPENVINO
# =========================================================
@app.route("/api/emergencia/procesar-frame-openvino", methods=["POST"])
def api_procesar_frame_openvino():

    model = get_openvino_model()
    if not model:
        return jsonify({"ok": False, "error": "Motor OpenVINO no disponible"}), 500

    data = request.get_json() or {}
    # frame_b64 = data.get("imagen_final")
    frame_data = data.get("frame")
    
    try:
        _, encoded = frame_data.split(",", 1)
        image_bytes = base64.b64decode(encoded)
        nparr = np.frombuffer(image_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        # Redimensionar a 640x640 (formato nativo de YOLOv11)
        input_img = cv2.resize(frame, (640, 640))
        input_img = input_img.transpose((2, 0, 1))
        input_img = np.expand_dims(input_img, axis=0).astype(np.float32) / 255.0

        output_layer = model.output(0)
        results = model([input_img])[output_layer]
        detections = results[0].transpose()

        boxes, confidences, class_ids = [], [], []
        for row in detections:
            scores = row[4:]
            class_id = np.argmax(scores)
            conf = scores[class_id]
            if conf > 0.45:
                nombre = COCO_CLASSES[class_id] if class_id < len(COCO_CLASSES) else "objeto"
                if nombre in MIS_CLASES:
                    xc, yc, ww, hh = row[:4]
                    # Coordenadas para el cálculo
                    x = int(xc - ww/2)
                    y = int(yc - hh/2)
                    w = int(ww)
                    h = int(hh)
                    boxes.append([x, y, w, h])
                    confidences.append(float(conf))
                    class_ids.append(int(class_id))

        indices = cv2.dnn.NMSBoxes(boxes, confidences, 0.45, 0.45)
        
        final_objs = []

        # 1. Listas de agrupación
        GRUPO_VEHICULOS = ['bicicleta', 'carro', 'moto', 'bus', 'camion']
        # 2. Inicializar conteo de grupos
        conteo_grupos = {
            "personas": 0,
            "vehiculos": 0,
            "perros":0,
            "otros": 0
        }

        if len(indices) > 0:
            for i in indices.flatten():
                clase_real = COCO_CLASSES[class_ids[i]]
                
                # Lógica de agrupación de conteo
                if clase_real == 'persona':
                    conteo_grupos["personas"] += 1
                elif clase_real == 'perro':
                    conteo_grupos["perros"] += 1
                elif clase_real in GRUPO_VEHICULOS:
                    conteo_grupos["vehiculos"] += 1
                elif clase_real in MIS_CLASES:
                    conteo_grupos["otros"] += 1

                # CORRECCIÓN AQUÍ: No sumamos de nuevo, usamos x1, y1, x2, y2 directamente
                # final_objs.append({
                #     "clase": clase_real,
                #     "confianza": round(confidences[i], 2),
                #     "bbox": [boxes[i][0], boxes[i][1], boxes[i][2], boxes[i][3]]
                # })
                final_objs.append({
                    "clase": clase_real,
                    "confianza": round(confidences[i], 2),
                    "bbox": [boxes[i][0], boxes[i][1], boxes[i][0] + boxes[i][2], boxes[i][1] + boxes[i][3]]
                })

        return jsonify({
            "ok": True,
            "objects": final_objs,
            "conteo": conteo_grupos, # Enviamos el conteo ya agrupado
            "imagen_procesada": frame_data
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500    


# Función para guardar las imagenes generadas posterior a la transmisión de 30 segundos
# 1. Crear carpeta para los mejores frames si no existe
MEJORES_FRAMES_FOLDER = os.path.join("static", "uploads", "images_transmission")
# MEJORES_FRAMES_FOLDER = os.environ.get("CLOUDINARY_FOLDER"),
os.makedirs(MEJORES_FRAMES_FOLDER, exist_ok=True)

@app.route("/api/emergencia/guardar-mejor-frame", methods=["POST"])
def api_guardar_mejor_frame():
    try:
        data = request.get_json()
        frame_b64 = data.get("imagen_final")
        
        if not frame_b64:
            return jsonify({"ok": False, "error": "No se recibió imagen"}), 400
        
        # Guardando la imagen en Servidor RENDER, ***************************
        # En esta nube se borran los archivos en cada Deploy
        # Decodificar la imagen base64
        _, encoded = frame_b64.split(",", 1)
        image_bytes = base64.b64decode(encoded)

        # Generar nombre único: mejor_deteccion_YYYYMMDD_HHMMSS.jpg
        nombre_archivo = f"mejor_deteccion_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        ruta_completa = os.path.join(MEJORES_FRAMES_FOLDER, nombre_archivo)

        # Guardar en el disco
        with open(ruta_completa, "wb") as f:
            f.write(image_bytes)

        print(f"Evidencia guardada automáticamente en: {ruta_completa}")
        # *******************************************************************

        # Guardando la imagen en la nube de CLOUDINARY ***************************
        # Subir directamente a Cloudinary (acepta el string base64 tal cual)
        upload_result = cloudinary.uploader.upload(
            frame_b64,
            folder = "incabit/uploads/images_transmission",
            public_id = f"mejor_deteccion_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            overwrite = True,
            resource_type = "image"
        )

        # La URL pública que usaremos para ver la imagen desde cualquier lugar
        url_publica = upload_result.get("secure_url")
        print(f"Evidencia subida a Cloudinary: {url_publica}")

        # --- RECOMENDACIÓN: AQUÍ DEBERÍAS ACTUALIZAR TU BASE DE DATOS
        # --- Si tienes el código del incidente, guarda 'url_publica' en la columna 'ruta_imagen'
        
        return jsonify({
            "ok": True, 
            "mensaje": "Imagen guardada en Cloudinary",
            "url": url_publica
        })
    except Exception as e:
        print(f"Error al guardar imagen: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500
    

# Esta función esta programada para trabajar con RUNPOD
@app.route("/api/emergencia/procesar-frame", methods=["POST"])
def api_procesar_frame():
    control = liberar_transmision_si_expirada()

    if control.estado != "activa":
        return jsonify({
            "ok": False,
            "error": "No hay una transmisión activa autorizada."
        }), 403

    data = request.get_json(silent=True) or {}
    frame_data = data.get("frame")  # Viene como data:image/jpeg;base64,...

    if not frame_data:
        return jsonify({"ok": False, "error": "No se recibió ningún frame"}), 400

    try:
        if "," not in frame_data:
            return jsonify({"ok": False, "error": "Formato de imagen inválido"}), 400

        _, encoded = frame_data.split(",", 1)
        image_bytes = base64.b64decode(encoded)
        nparr = np.frombuffer(image_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if frame is None:
            return jsonify({"ok": False, "error": "No se pudo decodificar el frame"}), 400
        
        # 1. Llamar a RunPod
        result = procesar_y_detectar(frame)

        if result is None:
            return jsonify({"ok": False, "error": "Sin respuesta de GPU"}), 200
        
        # 1. Crear un diccionario de conteo compatible con el JS del frontend
        conteo_formateado = {
            "person": 0,
            "car": 0,
            "motorcycle": 0,
            "bus": 0,
            "truck": 0,
            "dog": 0
        }

        # 2. Mapear las detecciones de RunPod al conteo
        # RunPod devuelve: [{"clase": "person", ...}, {"clase": "dog", ...}]
        if result and "objects" in result:
            for obj in result["objects"]:
                clase_detectada = obj["clase"]
                if clase_detectada in conteo_formateado:
                    conteo_formateado[clase_detectada] += 1

        # 3. Enviamos los datos crudos al celular
        return jsonify({
            "ok": True,
            "imagen_procesada": frame_data,
            "objects": result.get("objects", []), # CAMBIA 'detecciones' por 'objects'
            "conteo": conteo_formateado
        })

    except Exception as e:
        print(f"Error en procesamiento: {e}")
        return jsonify({
            "ok": False,
            "error": str(e),
            "detecciones": [],
            "conteo": 0
        }), 500


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
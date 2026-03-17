import os
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, flash

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "incabit-dev-key")

SITE = {
    "brand": "incaB1T",
    "tagline": "Detecta objetos, comportamientos, anticipa acciones",
    "email": "cesar@incabit.com",
    "phone": "+51 943002381",
    "whatsapp": "51943002381"
}

UPLOAD_FOLDER = os.path.join("static", "uploads", "emergencias")
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # 8 MB


@app.context_processor
def inject_site():
    return dict(site=SITE)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def generar_codigo_incidente():
    # Luego esto se reemplaza por BD/autoincremental real
    from datetime import datetime
    return f"INC-{datetime.now().strftime('%Y%m%d-%H%M%S')}"


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
        evidencia = request.files.get("evidencia")

        errores = []

        if not tipo_reporte:
            errores.append("Debes seleccionar el tipo de reporte.")

        if not descripcion:
            errores.append("Debes ingresar una descripción del incidente.")

        if not latitud or not longitud:
            errores.append("No se pudo obtener la ubicación. Activa el GPS del celular.")

        archivo_guardado = None

        if evidencia and evidencia.filename:
            if allowed_file(evidencia.filename):
                codigo_incidente = generar_codigo_incidente()
                extension = evidencia.filename.rsplit(".", 1)[1].lower()
                nombre_archivo = secure_filename(f"{codigo_incidente}.{extension}")
                ruta_archivo = os.path.join(app.config["UPLOAD_FOLDER"], nombre_archivo)
                evidencia.save(ruta_archivo)
                archivo_guardado = f"uploads/emergencias/{nombre_archivo}"
            else:
                errores.append("La imagen debe ser JPG, JPEG, PNG o WEBP.")
        else:
            errores.append("Debes adjuntar una imagen tomada o cargada desde el celular.")

        if errores:
            for error in errores:
                flash(error, "error")
            return render_template("emergencia_reportar.html", page_title="Reportar Emergencia")

        # Aquí luego guardaremos en PostgreSQL
        # print(tipo_reporte, descripcion, latitud, longitud, archivo_guardado)

        flash("Emergencia registrada correctamente.", "success")
        return redirect(
            url_for(
                "emergencia_estado",
                codigo=codigo_incidente,
                tipo=tipo_reporte
            )
        )

    return render_template("emergencia_reportar.html", page_title="Reportar Emergencia")


@app.route("/emergencia/estado/<codigo>")
def emergencia_estado(codigo):
    tipo = request.args.get("tipo", "")
    return render_template(
        "emergencia_estado.html",
        page_title="Estado de Emergencia",
        codigo=codigo,
        tipo=tipo
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
    app.run(debug=True, host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
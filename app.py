import os
from flask import Flask, render_template

app = Flask(__name__)

SITE = {
    "brand": "incaB1T",
    "tagline": "Detecta objetos, comportamientos, anticipa acciones",
    "email": "cesar@incabit.com",
    "phone": "+51 943002381",
    "whatsapp": "51943002381"
}

@app.context_processor
def inject_site():
    return dict(site=SITE)

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

@app.route("/casos-de-uso")
def casos():
    return render_template("casos.html", page_title="Casos de uso")

@app.route("/demo")
def demo():
    return render_template("demo.html", page_title="Demo")

@app.route("/contacto")
def contacto():
    return render_template("contacto.html", page_title="Contacto")

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
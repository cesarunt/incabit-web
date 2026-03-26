# incaB1T - Sitio Web en Flask

## Instalación
python -m venv venv

# Windows
venv\Scripts\activate
source venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
python app.py

## Ramas (git branch)
- main:     web inicial, información estática home, menu y contacto
- live:     web con streaming, detectando objetos (yolo), usando CPU en RENDER
- runpod:   web con streaming, detectando objetos (yolo), usando GPU Serverless en RUNPOD

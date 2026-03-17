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

## Rutas
- /
- /aprendizaje
- /plataforma
- /emergencia
- /soluciones
- /contacto

# Arquitectura inicial recomendada

## Ciudadano
Celular del ciudadano → navegador móvil → incabit.com/emergencia
Desde ahí:
- cámara
- micrófono
- GPS
- foto/video/transmisión

## Backend
Flask
- autenticación opcional
- API de incidentes
- carga de archivos
- registro de ubicación
- almacenamiento

## Almacenamiento
- evidencia multimedia en disco o cloud
- metadatos en PostgreSQL

## Panel de monitoreo
- operadores
- visualización de incidentes
- reproducción de videos
- revisión de imágenes


# Recomendación estratégica
Solución híbrida desde el inicio conceptual:

## Ciudadano
- usa celular
- transmite o reporta

## Municipio
- recibe
- visualiza
- gestiona

## IA
- entra como capa posterior
- no como requisito inicial
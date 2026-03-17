# Arquitectura física simplificada

Ciudadano (celular)
   │
   ├─ Cámara / Micrófono / GPS
   │
   ▼
PWA incabit.com/emergencia
   │
   ▼
Backend Flask
   │
   ├─ API Incidentes
   ├─ API Evidencias
   ├─ Gestión de estados
   │
   ├─ PostgreSQL
   └─ Almacenamiento multimedia
   │
   ▼
Panel Admin / Operador
   │
   ├─ Revisión de incidentes
   ├─ Visualización de evidencia
   ├─ Ubicación en mapa
   └─ Clasificación / atención


# Estructura sugerida del proyecto Flask

incabit/
│
├── app/
│   ├── __init__.py
│   ├── models/
│   ├── routes/
│   │   ├── public.py
│   │   ├── emergencia.py
│   │   ├── api.py
│   │   └── admin.py
│   ├── services/
│   │   ├── upload_service.py
│   │   ├── incident_service.py
│   │   └── location_service.py
│   ├── templates/
│   │   ├── emergencia/
│   │   └── admin/
│   └── static/
│
├── uploads/
├── migrations/
├── config.py
└── run.py

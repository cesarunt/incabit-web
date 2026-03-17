# Diagrama de arquitectura técnica

┌─────────────────────────────────────────────────────────────┐
│                    CIUDADANO / USUARIO                      │
│                  Celular Android / iPhone                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ Accede a
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 PWA WEB: incabit.com/emergencia             │
│                                                             │
│  Funciones del lado cliente:                                │
│  - Captura de foto                                          │
│  - Grabación de video corto                                 │
│  - Transmisión temporal                                     │
│  - Geolocalización                                          │
│  - Formulario de incidente                                  │
│  - Envío de evidencia                                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ HTTPS / API
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     BACKEND FLASK                           │
│                                                             │
│  Módulos principales:                                       │
│  - Gestión de incidentes                                    │
│  - Recepción de evidencias                                  │
│  - Validación de archivos                                   │
│  - Registro de ubicación                                    │
│  - Gestión de estados                                       │
│  - Autenticación admin                                      │
│  - API REST                                                 │
└─────────────────────────────────────────────────────────────┘
                 │                    │                   │
                 │                    │                   │
                 ▼                    ▼                   ▼
┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
│     POSTGRESQL       │  │ ALMACENAMIENTO MEDIA │  │   MÓDULO IA FUTURO   │
│                      │  │                      │  │                      │
│ - Incidentes         │  │ - Fotos              │  │ - YOLO               │
│ - Evidencias         │  │ - Videos             │  │ - Conteo personas    │
│ - Ubicaciones        │  │ - Clips temporales   │  │ - Detección objetos  │
│ - Usuarios           │  │ - Miniaturas         │  │ - Clasificación      │
│ - Historial          │  │                      │  │ - Alertas automáticas│
└──────────────────────┘  └──────────────────────┘  └──────────────────────┘
                              │
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                PANEL ADMIN / MUNICIPALIDAD                  │
│                  incabit.com/admin/incidentes               │
│                                                             │
│  Funciones:                                                 │
│  - Ver incidentes nuevos                                    │
│  - Revisar imágenes/videos                                  │
│  - Ver ubicación en mapa                                    │
│  - Cambiar estado                                           │
│  - Clasificar incidente                                     │
│  - Derivar atención                                         │
└─────────────────────────────────────────────────────────────┘


# Mapa General o Funcional de pantallas y módulos

INCABIT.COM
│
├── Inicio
├── Aprendizaje
├── Plataforma
├── Soluciones
├── Contacto
└── Emergencias
    │
    ├── Pantalla principal de emergencia
    ├── Reportar con foto
    ├── Reportar con video
    ├── Transmisión temporal
    ├── Confirmación de envío
    └── Consulta de estado
     
ADMIN
│
├── Login
├── Dashboard
├── Lista de incidentes
├── Detalle de incidente
├── Mapa de incidentes
└── Gestión de estados
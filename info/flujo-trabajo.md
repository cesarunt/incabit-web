# Flujo técnico resumido

1. Ciudadano abre incabit.com/emergencia
2. La PWA solicita permisos de cámara, micrófono y ubicación
3. El ciudadano captura foto / video o inicia transmisión temporal
4. El frontend envía datos al backend Flask
5. Flask registra el incidente en PostgreSQL
6. Flask guarda la evidencia en almacenamiento multimedia
7. El panel admin muestra el incidente en tiempo real o casi real
8. El operador revisa, clasifica y atiende
9. En una fase futura, la IA analiza la evidencia automáticamente


# Flujo funcional integral

CIUDADANO
   │
   ├─ Ingresa a /emergencia
   ├─ Elige foto / video / transmisión
   ├─ Comparte ubicación
   ├─ Agrega descripción
   └─ Envía reporte
        │
        ▼
BACKEND FLASK
   │
   ├─ Registra incidente
   ├─ Guarda ubicación
   ├─ Guarda evidencia
   └─ Genera código único
        │
        ▼
PANEL ADMIN
   │
   ├─ Lista incidente nuevo
   ├─ Revisa evidencia
   ├─ Evalúa prioridad
   ├─ Cambia estado
   └─ Atiende / deriva / cierra
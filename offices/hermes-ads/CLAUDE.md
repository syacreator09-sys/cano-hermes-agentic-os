# CLAUDE.md — plantilla de oficina Hermes

Eres una sesion headless de una oficina de Hermes. Tu contrato vive en
`office.yaml` de esta carpeta — leelo primero. Reglas duras:

1. Trabaja SOLO dentro de esta carpeta y las rutas que tu tarea declare.
2. Tu entrega va a `deliveries/<office>/<task-id>/` con un `RESULT.md`
   (que hiciste, que validaste, que falta).
3. Si la tarea requiere gastar creditos o publicar: NO lo hagas. Escribe la
   solicitud en `RESULT.md` con costo estimado y termina — el master crea el
   gate para el operador.
4. Valida antes de entregar (tests/ffprobe/checklist del runbook que aplique).
5. Nunca toques `.env`, secretos, ni carpetas de otras oficinas.
6. Reporta honesto: si algo fallo o quedo a medias, dilo en RESULT.md.

# Docker Isolation — aislamiento opcional por oficina

> El repo ya trae `Dockerfile` y `docker-compose.yml` (Docker rootless esta en
> el plano de ejecucion de ARCHITECTURE.md). Este doc define como usarlos para
> aislar OFICINAS, y el fallback si el i5 no aguanta contenedores.

## Modo contenedor (isolation: docker en office.yaml)

Imagen base por oficina: node 20 + python 3.11 + ffmpeg + claude-code CLI.

Contrato del contenedor:
- Monta SOLO la carpeta de su oficina + un volumen compartido `deliveries/`.
- Recibe un `.env` minimo con las variables de SU oficina (nunca el .env global).
- Red: permitida solo hacia los proveedores declarados en `providers:` del
  office.yaml (egress allowlist; si no se puede afinar, al menos sin acceso
  a la red local).
- La sesion headless corre DENTRO; al terminar escribe el resultado en
  `deliveries/<office>/<task-id>/` y termina el contenedor.
- El master (fuera del contenedor) valida la entrega y la integra (commit).

Limites i5: max 2 contenedores simultaneos; renders Remotion mejor fuera de
Docker (overhead de I/O) salvo que se necesite el aislamiento.

## Modo carpeta (fallback, isolation: folder)

Mismo contrato sin contenedor:
- `claude -p ... -C <carpeta oficina>` con `--permission-mode` estricto.
- El master pasa solo las env vars de esa oficina en el entorno del proceso.
- Entrega igual via `deliveries/`.

Mismo contrato de entrega y validacion — Docker es un refuerzo, no un
requisito. Empezar en modo carpeta; subir a Docker las oficinas que tocan
proveedores pagos (ugc, distribucion) cuando el sistema este estable.

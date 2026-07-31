# Política de Seguridad

Última actualización: 31 de julio de 2026.

## Alcance

Esta política cubre el núcleo de Cano Hermes Agentic OS, sus agentes, skills, herramientas, proveedores de modelos, Nexus, contenedores, integraciones externas y procesos de desarrollo.

## Principios obligatorios

- modo seguro por defecto;
- privilegio mínimo;
- separación de workspaces y memorias;
- secretos fuera de Git;
- aprobación humana para acciones sensibles;
- trazabilidad de cambios y decisiones;
- rollback antes de operaciones irreversibles;
- cuarentena para capacidades importadas.

## Acciones que requieren aprobación

- llamadas API de pago por encima del presupuesto autorizado;
- publicación de contenido;
- envío de mensajes externos;
- despliegues y cambios productivos;
- acceso o modificación de datos empresariales;
- creación o rotación de credenciales;
- operaciones destructivas;
- cambios de permisos;
- merges a ramas protegidas.

## Secretos

Nunca deben almacenarse en Git:

- API keys;
- tokens OAuth;
- contraseñas;
- cookies y sesiones;
- certificados privados;
- credenciales de bases de datos;
- webhooks secretos;
- archivos `.env` reales.

Los secretos deben inyectarse mediante variables de entorno, servicios de secretos o credenciales temporales y limitadas.

## Agentes y runtimes

- Claude Code y Codex trabajan en worktrees o directorios separados.
- Ningún agente puede editar simultáneamente los mismos archivos que otro worker.
- Los agentes no reciben acceso directo a `/var/run/docker.sock`.
- OpenClaw, Hermes Agent y workers externos deben ejecutarse con permisos delimitados.
- Las capacidades nuevas pasan por `candidate → quarantine → review → approved → active`.
- Los agentes no aprueban su propio trabajo sensible.

## Docker y ejecución de código

- utilizar Docker rootless cuando sea posible;
- limitar CPU, memoria, tiempo y filesystem;
- negar red por defecto y usar allowlists;
- montar únicamente directorios necesarios;
- no ejecutar contenedores privilegiados;
- no compartir secretos maestros;
- destruir entornos temporales al finalizar.

## Memoria y Nexus

Los agentes reciben contexto mínimo mediante Context Builder. Las escrituras a la memoria global deben proponerse como candidatas y revisarse antes de promoción. La memoria de clientes, proyectos y canales debe permanecer separada.

## Proveedores externos

Cada proveedor debe tener:

- perfil de costo;
- límites de uso;
- permisos por agente;
- redacción de datos sensibles;
- fallback controlado;
- interruptor de desactivación;
- registro de consumo y errores.

## Reporte de vulnerabilidades

No publiques vulnerabilidades, credenciales o datos sensibles en issues públicos. Reporta el problema de forma privada al propietario del repositorio mediante la cuenta `syacreator09-sys`, incluyendo:

1. componente afectado;
2. impacto estimado;
3. pasos de reproducción seguros;
4. evidencia sin secretos;
5. recomendación de mitigación.

## Respuesta a incidentes

1. aislar el componente;
2. revocar accesos afectados;
3. rotar credenciales;
4. preservar evidencia;
5. corregir la causa;
6. revisar alcance;
7. documentar acciones;
8. restablecer solamente después de aprobación.

## Repositorio público

Este repositorio debe permanecer libre de datos reales, secretos y configuración productiva. Antes de conectar infraestructura, cuentas, clientes o credenciales reales, se recomienda cambiar la visibilidad del repositorio a **Private**.

La política técnica ampliada está en [`docs/SECURITY.md`](docs/SECURITY.md).

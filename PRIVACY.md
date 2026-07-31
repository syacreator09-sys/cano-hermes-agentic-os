# Política de Privacidad y Manejo de Datos

Última actualización: 31 de julio de 2026.

## Alcance

Esta política describe cómo Cano Hermes Agentic OS debe tratar información personal, empresarial, credenciales, archivos, memoria, métricas y datos provenientes de servicios externos.

## Principios

1. **Mínimo acceso:** cada agente recibe únicamente el contexto, archivos y herramientas necesarios para su tarea.
2. **Separación:** memoria global, proyectos, clientes, canales y workspaces deben permanecer aislados por namespace y permisos.
3. **Sin secretos en Git:** claves API, tokens OAuth, contraseñas, certificados, cookies y credenciales nunca deben almacenarse en el repositorio.
4. **Aprobación humana:** enviar mensajes, publicar, desplegar, gastar, modificar producción o ejecutar acciones destructivas requiere aprobación explícita.
5. **Trazabilidad:** las operaciones relevantes deben registrar actor, propósito, fecha, resultado y artefactos, sin exponer secretos.
6. **Retención limitada:** los datos temporales deben eliminarse cuando dejen de ser necesarios para la tarea o para auditoría autorizada.
7. **Privacidad por defecto:** los proveedores externos y las integraciones permanecen desactivados hasta configurarse deliberadamente.

## Categorías de datos

Hermes puede manejar, cuando se configure:

- solicitudes y conversaciones del propietario;
- archivos, notas y documentos de proyectos;
- repositorios y código fuente;
- métricas de contenido y operación;
- configuraciones de agentes, skills y herramientas;
- eventos, aprobaciones, costos y resultados;
- datos obtenidos de integraciones autorizadas.

## Credenciales

Las credenciales deben almacenarse fuera de Git mediante variables de entorno, secretos del sistema operativo o un secret manager. Los workers reciben credenciales temporales y de alcance limitado. Ningún agente debe recibir todas las claves del sistema.

## Memoria y Nexus

Las notas de Obsidian, relaciones de Graphify y memorias persistentes se consideran información privada. El Context Builder debe entregar únicamente fragmentos relevantes. Los agentes proponen nuevas memorias como candidatas; no escriben directamente en la memoria global sin revisión.

## Proveedores de modelos

Al usar Anthropic, OpenAI, Moonshot, DeepSeek, Qwen, xAI u otros proveedores, solamente se enviará el contexto necesario. La configuración debe permitir excluir información sensible o ejecutar tareas localmente cuando corresponda.

## Logs y auditoría

Los logs no deben incluir claves, tokens, cookies, encabezados de autorización ni contenido sensible completo. Deben aplicar redacción antes de persistir errores, prompts, respuestas o trazas.

## Derechos y control del propietario

El propietario puede revisar, corregir, exportar o eliminar los datos almacenados por Hermes. Las operaciones de borrado permanente requieren confirmación y registro de auditoría.

## Incidentes

Ante una exposición de datos o credenciales:

1. detener el componente afectado;
2. revocar y rotar credenciales;
3. preservar evidencia sin divulgar secretos;
4. identificar alcance y causa;
5. corregir la vulnerabilidad;
6. documentar el incidente y las acciones tomadas.

## Repositorio público

Este repositorio no debe contener datos personales, secretos, endpoints privados, documentos empresariales ni configuraciones productivas. Antes de integrar información real, se recomienda cambiar su visibilidad a **Private**.

## Contacto

Responsable del proyecto: Cano / `syacreator09-sys`.

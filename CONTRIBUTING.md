# Guía de Contribución

Cano Hermes Agentic OS es un proyecto controlado por su propietario. Las contribuciones no se integran automáticamente y deben respetar la arquitectura, seguridad y separación de sistemas definida en el repositorio.

## Reglas obligatorias

- No trabajar directamente sobre `main`.
- Crear una rama por cambio.
- No incluir claves, tokens, cookies, certificados ni datos privados.
- No conectar producción, publicar, gastar ni desplegar sin aprobación explícita.
- No dar acceso al socket de Docker a agentes o contenedores.
- No mezclar Cano AI Command Center dentro del núcleo de Hermes.
- Factory V5 debe permanecer como sistema externo conectado por contrato.
- Claude Code y Codex deben usar workspaces o worktrees separados.
- Los agentes, skills, plugins y MCP nuevos comienzan en estado candidato o cuarentena.

## Flujo recomendado

```text
SPEC
→ BUILD
→ REVIEW
→ FIX
→ APPROVAL
→ MERGE
```

La ejecución de pruebas, lint, workflows o despliegues debe realizarse solamente cuando el propietario lo autorice.

## Cambios aceptables

- mejoras al núcleo de orquestación;
- nuevos agentes o skills con manifiesto y permisos claros;
- adaptadores de proveedores;
- mejoras a Nexus y Context Builder;
- documentación, seguridad y observabilidad;
- interfaces y experiencia de usuario;
- integraciones externas desacopladas.

## Requisitos de una propuesta

Cada cambio debe explicar:

1. problema que resuelve;
2. archivos modificados;
3. permisos necesarios;
4. riesgos;
5. comportamiento de rollback;
6. dependencias nuevas;
7. impacto en costos y privacidad.

## Convenciones

- Python moderno y tipado cuando sea razonable.
- Configuración mediante variables de entorno.
- Logs sin secretos.
- Operaciones sensibles detrás de aprobaciones.
- Componentes pequeños y desacoplados.
- Documentación actualizada junto con el código.

## Seguridad

Las vulnerabilidades no deben publicarse en issues abiertos. Consulta [SECURITY.md](SECURITY.md).

## Licencia

Toda contribución aceptada queda sujeta a la licencia propietaria del repositorio y no concede derechos de reutilización fuera del proyecto.

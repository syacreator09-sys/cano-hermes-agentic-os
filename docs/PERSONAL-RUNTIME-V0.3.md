# StarHome Personal Runtime v0.3

## Estado

Este paquete amplía StarHome OS de forma aditiva. No despliega, no publica, no mueve dinero, no opera inversiones y no modifica sistemas externos. Todos los agentes y skills nuevos permanecen en estado `candidate`.

## Contrato de acciones

Cada manifiesto puede declarar:

- `description`: función operativa y límite del agente;
- `actions.allowed`: acciones preparatorias que puede realizar dentro del workspace;
- `actions.approval_required`: acciones que solo pueden pasar a un adaptador externo después de aprobación;
- `actions.prohibited`: acciones que nunca debe ejecutar ese agente.

El contrato es retrocompatible: los agentes existentes sin estos campos continúan validando con listas vacías. Una acción no puede aparecer en más de una categoría.

## Coordinadores incluidos

| Agente | Descripción | Permitido | Con aprobación | Prohibido |
|---|---|---|---|---|
| `chief-of-staff` | Prioriza el día y consolida pendientes. | Briefs, captura y revisión semanal. | Calendario, mensajes y tareas externas. | Dinero, producción y exposición de datos. |
| `finance-controller` | Prepara posición financiera y conciliaciones. | Gastos, conciliación, flujo y cierre. | Escrituras financieras, importaciones y exportaciones. | Pagos, transferencias, trading y alteración de estados. |
| `revenue-operator` | Ordena leads y próximas acciones. | Resúmenes, recomendaciones, propuestas y pipeline. | Mensajes, CRM, citas y cotizaciones. | Firmas, cobros y exposición de clientes. |
| `project-operator` | Consolida estado, bloqueos y entregables. | Estado, bloqueos, planes y siguiente acción. | Repositorios, gestores, despliegues y asignaciones externas. | Merge a `main`, producción y borrado de proyectos. |
| `content-intelligence-director` | Convierte investigación en briefs para Factory V5. | Señales, scoring, briefs y contratos borrador. | Jobs, créditos, identidad y publicación. | Autopublicar, copiar, claims sin verificar y saltar revisión. |
| `investment-intelligence` | Analiza tesis, escenarios y riesgo. | Investigación, tesis, escenarios y riesgo. | Alertas, snapshots y exportaciones. | Operar, cerrar posiciones, transferir fondos o prometer retornos. |
| `document-auditor` | Audita copias preservando evidencia. | Inspección, comparación, cálculos y reporte. | Copias redactadas y compartir informes. | Alterar, falsificar, borrar evidencia o exponer datos. |
| `learning-coach` | Mantiene sesiones y progreso formativo. | Sesiones, glosario, ejercicios y evaluación. | Actualizar expediente, inscribir cursos o enviar materiales. | Inventar fuentes, acreditar o entregar trabajo como el usuario. |

## Skills incluidas

### Personal Operations

- `daily-brief`
- `capture-anything`
- `weekly-review`

### Finance

- `expense-capture`
- `cash-position`
- `finance-close`

### Revenue

- `lead-next-action`
- `pipeline-review`

### Projects

- `project-status`
- `blocker-review`

### Specialists

- `content-opportunity-brief`
- `investment-thesis-review`
- `document-consistency-audit`
- `learning-session`

## Validación

En un checkout limpio de la rama:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
python scripts/validate.py
pytest -q
ruff check \
  cano_hermes/domain/models.py \
  tests/test_agent_action_contract.py \
  tests/test_personal_runtime_pack.py
```

Resultado esperado:

- 46 agentes válidos;
- 54 skills registradas;
- pruebas completas en verde;
- lint de los archivos modificados en verde;
- ocho agentes nuevos en `candidate`;
- catorce skills nuevas en `candidate`.

## Promoción

La promoción debe hacerse individualmente:

```text
candidate → quarantine → testing → approved → active
```

Antes de promover una capacidad:

1. ejecutar sus evaluaciones declaradas;
2. probar con datos sintéticos o copias;
3. revisar permisos y acciones;
4. confirmar que no requiere secretos globales;
5. obtener aprobación humana;
6. registrar versión y decisión en Nexus.

No se promueve el paquete completo de una sola vez.

## Rollback

Mientras el PR permanezca sin fusionar, el rollback seguro es cerrar el PR y eliminar la rama.

Después de una futura fusión, el rollback debe revertir el merge completo. No se eliminan ni reescriben agentes existentes.

## Exclusiones de v0.3

Esta versión no incluye:

- conexión bancaria;
- escrituras en Supabase;
- Gmail o Calendar;
- CRM;
- WhatsApp o Telegram;
- Factory V5 real;
- proveedores premium;
- Claude Code o Codex autenticados;
- Cloudflare Workflows;
- despliegue o publicación;
- trading o pagos.

Estas integraciones requieren ramas y revisiones independientes.

# expense-capture

Preparar un registro de gasto personal o empresarial con evidencia, clasificación y control de duplicados.

## Procedure

1. Extraer únicamente monto, moneda, fecha, concepto, cuenta y entidad explícitos.
2. Conservar la entrada o comprobante original como evidencia.
3. Buscar posibles duplicados por monto, fecha, concepto y cuenta.
4. Proponer categoría y entidad, marcando cualquier inferencia.
5. Presentar el registro para aprobación antes de escribir en una fuente financiera externa.

## Verification

- El monto debe conservar precisión y moneda.
- La entidad personal o empresarial debe quedar separada.
- Los campos ausentes permanecen como desconocidos.
- No se modifica saldo ni se mueve dinero sin aprobación.

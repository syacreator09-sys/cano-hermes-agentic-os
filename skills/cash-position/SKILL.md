# cash-position

Calcular efectivo disponible, comprometido y proyectado por entidad sin confundir saldo con capital utilizable.

## Procedure

1. Reunir saldos, efectivo, cuentas por cobrar, cuentas por pagar, deudas y apartados con fecha de corte.
2. Separar datos por entidad antes de consolidar.
3. Calcular saldo bruto, dinero comprometido, disponible operativo y obligaciones próximas.
4. Señalar registros desactualizados, no conciliados o sin fuente.
5. Preparar el reporte para aprobación antes de persistir resultados fuera del workspace.

## Verification

- Toda cifra debe indicar fecha, moneda y fuente.
- La suma consolidada debe reconciliar con sus componentes.
- No contar cuentas por cobrar como efectivo disponible.
- No iniciar transferencias, pagos o movimientos sin aprobación.

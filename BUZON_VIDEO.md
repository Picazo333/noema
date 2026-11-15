# Buzón — Loop de vídeo (sprint Higgsfield v4)

Este archivo existe solo para que este PR permanezca abierto como **buzón permanente** del loop de vídeo. **No se fusiona.**

## Cómo funciona

- Moncho publica aquí, como **comentario en este PR**, una señal por evento del loop.
- La sesión de vídeo (Codex / Work) lee los comentarios de este PR y actúa según la señal.
- Formato exacto de la señal (un comentario por evento):

```
[SEÑAL-VIDEO] JOB_INICIADO
pieza: <pieza>
job_id: <job_id>
lote: <lote>
estado: JOB_INICIADO
carpeta_drive: <SALIDA del lote> — https://drive.google.com/drive/folders/<id de la SALIDA>
hora_cdmx: YYYY-MM-DD HH:MM
```

Variante `HANDOFF_PENDIENTE` con el mismo esquema (estado: `HANDOFF_PENDIENTE`).

## Reglas

- Un comentario por evento. La sesión lee el comentario disparador Y todos los `[SEÑAL-VIDEO]` no procesados (varias señales cercanas pueden agruparse en una sola ejecución).
- Anti-duplicado por `job_id`: nunca generar dos veces el mismo `job_id`.
- No borrar las señales del PR: se limpian en el harvest (cerrar el PR y abrir uno nuevo, o dejarlas como auditoría).
- Orden maestro del loop: PELI-15 → BB-03 (Genjutsu) → BB-01 → BB-02 → BB-04 → BB-05 → GENJ-01 → GENJ-02 → GENJ-03 → GENJ-04 → PELI-16 → … → PELI-32.

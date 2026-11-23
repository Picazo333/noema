# ESTADO · noema

Actualizado: 23 nov 2026, hora de CDMX (curaduría de ramas). Archivo corto de portabilidad: con esto se retoma el repo en cualquier herramienta.

## Qué es
Sin descripción en GitHub; ver los archivos de la raíz.

## Cómo arrancar
Entorno de Python: `pip install -r requirements.txt` (o el `pyproject.toml`). Detalle en el README. Más contexto: `AGENTS.md`, `README.md`.

## Rama principal
`main` en `40bfdadf17396d8a19a82ccd8b1736bae22b16fd` antes de este PR.

## PRs vivos
- #6 `proposal/agent-succession-frontier` → `main`: Proposal: agent succession, execution frontier, and resume verification
- #8 `harvest/contract-id-namespace-integrity` → `main`: Noema harvest: contract ID namespace integrity
- #21 `buzon-video-loop` → `main`: Buzón — Señales del loop de vídeo [SEÑAL-VIDEO]
- #22 `noema/fase-3b-apuntador-indice` → `main`: Apuntador al índice unificado de Noema

## Ramas vivas o protegidas
- `buzon-video-loop`, `harvest/contract-id-namespace-integrity`, `noema/fase-3b-apuntador-indice`, `proposal/agent-succession-frontier`
- Ramas archivadas: tags `archivo/<rama>-23nov` (ver `git tag -l "archivo/*"`).

## Secretos que no van en el repo
Llaves de API, tokens, `.env`, credenciales de nube y datos personales: nunca en Git. Se guardan fuera (gestor de secretos o variables de entorno); en el repo solo pueden ir nombres de variables o un `.env.example` sin valores.

## Dónde se retoma
Este PR (`curaduria/estado-vigente-23nov`). Integra: `harvest/contract-id-namespace-integrity`, `noema/fase-3b-apuntador-indice`. Índice general: `/workspace/INDICE_ESTADO.md` (caja de Grok Bot).

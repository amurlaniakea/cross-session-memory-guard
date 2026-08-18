# CrossSessionMemoryGuard

[![License: AGPL-3.0-or-later](https://img.shields.io/badge/license-AGPL--3.0--or--later-blue.svg)](LICENSE)
[![CI](https://github.com/amurlaniakea/cross-session-memory-guard/actions/workflows/ci.yml/badge.svg)](https://github.com/amurlaniakea/cross-session-memory-guard/actions/workflows/ci.yml)

Guard de exfiltración de memoria cross-session para agentes LLM multi-tenant:
un **sensor read-only** que observa si un agente con memoria persistente está
filtrando datos de una sesión/usuario a otra sesión/usuario de forma no
autorizada — el ángulo de **confidencialidad read-time** de la memoria
compartida (Claude Cowork, agentes con memoria compartida entre usuarios).

Ortogonal a `memlineage` (integridad/procedencia write-time) y al OWASP Agent
Memory Guard (defensa write-side contra envenenamiento, ASI06): aquí la
pregunta no es "¿puede alguien corromper mi memoria?" sino
**"¿debería ESTE dato SALIR hacia ESTE principal?"**.

> **Estado: MVP (v0.1).** Spec cerrada y benchmark multi-tenant verdes; pendiente
> auditoría externa en clon fresco antes del primer release. No usar en
> producción aún.

## Por qué existe

- El estándar OWASP Top 10 for Agentic Applications 2026 (ASI01-ASI10) **no
  tiene categoría de confidencialidad cross-principal**: ASI06 es poisoning
  (write-side). Hueco de estándar documentado en `docs/RESEARCH.md`.
- Persistence-based memory extraction ("Isolated but Exposed", arXiv
  2607.23444) demuestra el vector: un agente aislado por sesión puede
  **extractar** memoria persistente de otros principios.
- Los repos existentes son adyacentes pero ninguno cubre el ángulo read-side
  (señal de gap: 0 repos para 5 términos exactos de búsqueda, ver
  `docs/RESEARCH.md`).

## Principios no negociables (Constitución §2)

1. **Read-only**: el sensor nunca bloquea, modifica, cuarentena ni participa
   en autorización. Fuera del camino crítico con fail-open estructural.
2. **Fail-open**: un error de adaptador degrada el escaneo (`degraded`), nunca
   lo aborta ni rompe al agente.
3. **Kill-switch**: `CSMG_DISABLED=1` desactiva el sensor por completo.
4. **Opacidad causal**: el evento nunca lleva el contenido íntegro del chunk —
   solo hash SHA-256 + span mínimo (≤200 chars).

## Señales de detección

| Señal | Qué compara | Qué detecta |
|---|---|---|
| (a) `mismatch` | procedencia resuelta vs. principal observador | filas de otro principal servidas por el retriever |
| (b) `similarity` | contenido vs. referencias de OTROS principales (umbral 0.75, simhash/jaccard) | contenido ajeno legible (incluye relabeling) |
| (c) `flowgraph` | grafo escritura→lectura rehidratado por capa esquema | lecturas sobre chunks escritos por otro principal |

Detección por el **path real de recuperación** del agente (KI-9); atribución
de escritura/referencias por **capa esquema** — quién OWNS cada chunk, nunca
la vista observada (KI-8). Limitaciones y decisiones en `KNOWN_ISSUES.md`.

## Instalación

```bash
python -m venv .venv
.venv/bin/pip install -e .
```

## Uso (CLI)

```bash
# Auditoría read-only de un almacén SQLite multi-tenant
csmg audit --store sqlite --path memoria.db --table mem --principal alpha

# Auditoría sobre JSONL
csmg audit --store jsonl --path eventos.jsonl --principal alpha

# Reporte del último escaneo
csmg report

# Desactivar completamente (kill-switch)
CSMG_DISABLED=1 csmg audit ...
```

Los eventos se emiten como JSONL append-only (`csmg-events/events.jsonl`),
con hash + span del chunk (nunca su contenido).

## Benchmark

Fixture determinista multi-tenant (3 tenants × 12 filas + adversarial
parametrizado) con escenarios: fuga en capa retriever (t1), plantado (t2),
robo de etiqueta (t3), collusión compuesta bajo umbral (t4, limitación
declarada AC7), baseline limpio (`correct`) y duplicación legítima adversarial
(`benign`). Umbrales declarados antes de correr; ASR + precision/recall/fp_rate
por señal derivados de los mismos eventos crudos (CSMG-055).

```bash
.venv/bin/python -m benchmark.runner
.venv/bin/python -m pytest -q
```

Resultados (seeds 1-3): t1/t2 ASR 0.0 (12/12, 1/1 detectadas); `correct` 0
eventos; `benign` fp_rate 0.071 (≤ tolerancia declarada 0.30). Tabla completa
de precision/recall por señal en la salida del runner.

## Licencia

**AGPL-3.0-or-later** — [ver LICENSE](LICENSE).

- Copyright (C) 2026 Pedro Sordo Martínez — amurlaniakea@gmail.com

Este proyecto es software libre: puede redistribuirlo y/o modificarlo bajo los
términos de la GNU Affero General Public License versión 3 o (a su elección)
cualquier versión posterior. Para más detalles, ver el archivo [LICENSE](LICENSE).
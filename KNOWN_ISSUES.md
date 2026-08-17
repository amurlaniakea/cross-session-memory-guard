# Known Issues (KI) — CrossSessionMemoryGuard

Registro de limitaciones y decisiones de arquitectura aceptadas. Un KI no es
un bug abierto: es una restricción conocida, documentada con su porqué, su
impacto y (cuando existe) el plan para resolverla. Los hallazgos de la
auditoría externa y del benchmark entran aquí ANTES de considerarse cerrados.

---

## KI-8 — Atribución de escritura: capa ESQUEMA, nunca la vista observada

**Estado:** resuelto en adaptadores JSONL/SQLite (`schema_chunks`); riesgo
abierto para los demás adaptadores (ver KI-11).

**Problema (demostrado por el propio benchmark, escenario t1):** rehidratar el
FlowGraph (quién escribió qué) y construir las referencias de similitud desde
la vista OBSERVADA (`list_chunks`) contamina la atribución: si el retriever
cruza tenants (el fallo que se está auditando), las filas ajenas aparecen como
"propias" y las señales (b)/(c) disparan sobre la contaminación, no sobre la
fuga. Números antes/después del fix en t1: `flowgraph 24 / similarity 26` →
`flowgraph 12 / similarity 13` (12 reales).

**Decisión:** la atribución (rehidratación + referencias) sale de la capa
ESQUEMA (`schema_chunks(principal)`: quién OWNS cada chunk), que no pasa por
el motor de recuperación. La detección sigue observando el path real
(`list_chunks`, KI-9). Son preguntas distintas: KI-9 = qué ve el auditado;
KI-8 = cómo se establece la verdad de quién escribió qué para comparar.

**Implementación:** `_attributed_chunks()` en `scan.py`; `schema_chunks()` en
`JsonlAdapter` y `SqliteGenericAdapter`.

---

## KI-9 — Detección sobre el path real de recuperación (read-time honesto)

**Estado:** vigente — RATIFICADO por el spike de enumeración (2026-08-17,
KI-10): el adaptador Engram PERMANECE schema-scoped, ahora por límite
ESTRUCTURAL demostrado del motor, no por decisión provisional.

**Decisión:** la detección observa el path REAL por el que el agente recupera
(`list_chunks(principal)`, con retriever opcional = el motor real). El adaptador
Engram queda declarado **schema-scoped**: no usa `engram search` como vía de
detección porque el spike F1 (2026-08-17, evidencia en
`docs/evidence/engram_search_spike_2026-08-17.txt`) demostró que es
**estructuralmente imposible enumerar** con el motor de búsqueda real:
(a) query vacía → `error: search query is required`; (b) comodines/escapes FTS
(`*`, `*:*`, `**`, `-`) → 0 resultados; (c) **cap duro de 20 resultados por
query** (irrelevante `--limit` ≥ 20; default 10); (d) la cobertura es función
del conjunto de queries: 15 queries amplias → 87.9% (80/91), 23 → 96.7%,
28 (incluyendo queries armadas con los términos de las filas que faltaban) →
100% — circular: para enumerar hay que saber ya qué buscar. Cualquier fila que
matchee una query pero quede fuera de su top-20 es invisible para ella
(blind spot silencioso de la vía real). El mapeo resultado→chunk_id SÍ existe
(`#<id>` en el output); el coste es ~0.5-0.6 s/llamada sin rate limit local.
La Fase 2 (reimplementar `list_chunks` sobre `engram search`) NO se ejecuta a
propósito: forzarla sería fingir una cobertura que el motor no garantiza
(principio de Sil: "no se puede, y así de bien lo entendemos").

**Impacto:** con Engram (producción), el sensor ve la capa de esquema, no lo
que el motor serviría con un filtro roto — cobertura honestamente parcial.
Es la única vía DETERMINISTA de enumeración disponible: el SELECT schema-scoped
directo sigue siendo la atribución de verdad (KI-8) y la detección observa la
única enumeración fiable, con la limitación documentada.

---

## KI-10 — Spike B5 (pendiente): enumeración vía `engram search`

**Estado:** RESPONDIDO por el spike F1 (2026-08-17) — evidencia cruda en
`docs/evidence/engram_search_spike_2026-08-17.txt`, datos incómodos incluidos.

Respuestas a las tres preguntas del spike B5:

1. **¿Query equivalente a "enumerar"? NO EXISTE.** Query vacía → error;
   comodines y escapes FTS → 0 resultados; cap duro de 20 por query
   (`--limit 1000`/`5000` siguen dando 20); la cobertura de una batería de
   queries es parcial (87.9% con 15, 96.7% con 23) y solo llega al 100% con
   queries hechas a medida de las filas que faltan — se necesita conocer de
   antemano el vocabulario de cada chunk (circular; blind spot silencioso de
   la vía real).
2. **Mapa resultado → chunk_id:** SÍ — el output expone `#<id>` (id directo
   de `observations`), parseable con `^\[\d+\] #(\d+)`.
3. **Coste:** ~0.5-0.6 s por llamada (16 llamadas ≈ 10 s); sin rate limit
   observado (binario local); banner "Update available" en stdout de todas
   las llamadas (ruido a filtrar).

**Conclusión:** límite ESTRUCTURAL del motor Engram — no hay forma fiable de
enumerar "todo lo visible para un principal" vía `engram search`. Fase 2 no
se ejecuta (forzar `list_chunks` sobre search fabricaría cobertura). El
adaptador Engram permanece schema-scoped (KI-9), con la limitación declarada.

---

## KI-11 — Adaptadores externos sin `schema_chunks`: fallback contaminante

**Estado:** documentado ANTES de B6 (hallazgo del auditor); trabajo futuro.

**Problema:** `schema_chunks()` solo existe en `JsonlAdapter` y
`SqliteGenericAdapter`. `Mem0Adapter`, `LangMemAdapter`, `ZepAdapter` y
`LettaAdapter` NO lo tienen, y `_attributed_chunks()` cae a `adapter.list_chunks()`
— la vía real de recuperación (KI-9). Consecuencia: si el filtro del motor
(mem0 `filters=user_id`, namespace de LangMem, etc.) estuviera roto y cruzara
tenants, la atribución de escrituras y las referencias de similitud se
contaminarían EXACTAMENTE como el bug t1 que KI-8 resolvió para SQLite/JSONL —
el mismo bug, sin el mismo fix. Hoy queda invisible porque estos adaptadores
solo se prueban con fakes y no están en el benchmark real.

**Decisión futura (on the record):** cuando mem0/langmem/zep/letta entren al
benchmark (fuera del MVP), necesitan su propia fuente de verdad ESQUEMA-scoped
para atribución/referencias (p. ej. consulta directa a su almacén por
`user_id`/`namespace`), nunca reusar la vía observada. Antes de integrarlos,
cada adaptador debe implementar `schema_chunks()` con la semántica documentada
en `scan.py`.

**Mitigación hoy:** los adaptadores externos son best-effort y su fallback
queda registrado aquí; el único adaptador de producción (Engram) usa
`list_principals`+schema-scoped y su atribución se considera ficcional para
las señales que dependen de referencias (KI-9).
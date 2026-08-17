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

**Estado:** vigente.

**Decisión:** la detección observa el path REAL por el que el agente recupera
(`list_chunks(principal)`, con retriever opcional = el motor real). El adaptador
Engram queda declarado **schema-scoped**: no usa `engram search` como vía de
detección porque (a) es búsqueda por relevancia, no enumeración, y (b) no se
ha verificado empíricamente que una query vacía/comodín devuelva la totalidad
de chunks visibles (riesgo de blind spot silencioso: top-N de nada). Probado
en solo lectura antes de comprometerse (spike B0).

**Impacto:** con Engram (producción), el sensor ve la capa de esquema, no lo
que el motor serviría con un filtro roto — cobertura honestamente parcial.

---

## KI-10 — Spike B5 (pendiente): enumeración vía `engram search`

**Estado:** pendiente, no bloqueante. Se anunció tras B5 y se persiste aquí.

**Preguntas abiertas** para cuando el adaptador Engram se reimplemente sobre la
vía real:

1. ¿Con qué query se llama a `engram search` para que el resultado sea
   equivalente a "enumerar todo lo visible para este principal"? Si la
   respuesta es "query vacía/comodín", verificar EMPÍRICAMENTE que el motor
   devuelve todo (o una muestra representativa declarada) y no el top-N más
   relevante de nada — si trunca, el sensor tiene un blind spot silencioso.
2. Mapa resultado → `chunk_id` (¿el resultado expone el id del chunk?).
3. Coste por llamada (¿rate limits? ¿coste de embeddings?).

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
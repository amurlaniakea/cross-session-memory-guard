# RESEARCH — Base de evidencia del nicho

Investigación de nicho realizada el **2026-08-17** (método
`METODOS/Metodo_Encuentra_Nicho.md` del vault; checklist 6/6). Esta nota es la
evidencia cruda que sostiene la Spec (SPEC §8) — cada afirmación cita su vía
de verificación concreta.

## 1. El gap

**Confidencialidad read-time de memoria compartida multi-tenant**: un agente
con memoria persistente puede *filtrar* datos de una sesión/usuario a otra
sesión/usuario de forma no autorizada. Los proyectos existentes cubren
integridad/procedencia write-time (`memlineage`, OWASP Agent Memory Guard,
dent8, Obex) — nadie vigila la salida de datos por el camino de recuperación.

## 2. Señal de gap (verificada por dos vías)

`gh api` / `api.github.com` (2026-08-16/17), 5 términos exactos:

| Término | Resultados |
|---|---|
| `agent memory exfiltration guard` | 0 |
| `memory exfiltration detector` | 0 |
| `cross-tenant data leakage detection` | 0 |
| `session data leakage detection agent` | 0 |
| `memory provenance read-only monitor agent` | 0 |
| Control: `agent persistent memory` | 4,632 (4,631 el 16-08; +1 delta de conteo vivo) |
| Control: `topic:llm-memory` | 435 |

Repos adyacentes auditados (metadata por `gh api`, verificada por dos vías;
READMEs leídos): **OWASP Agent Memory Guard** (125★, Apache-2.0, write-side
ASI06), **aigis** (54★, Apache-2.0, firewall de tool-calls), **dent8** (4★,
Apache-2.0, pushed 2026-07-30), **Obex** (0★, MIT, pushed 2026-07-22),
**governed-agent-memory** (2★, sin licencia, pushed 2026-07-15),
**agent-memory-lab** (0★, MIT, pushed 2026-08-12). **Ninguno cubre el ángulo
read-side.** Controles de tamaño del espacio: agentmemory 27,111★; cognee
30,079★; engram 6,028★.

## 3. Papers (16 verificados por `id_list` contra export.arxiv.org)

Ancla:

- **2607.23444 — "Isolated but Exposed: Persistence-Based Memory Extraction
  Attack on LLM Agents"** (2026-07-26). El ataque de extracción de memoria
  persistente sobre agentes aislados por sesión: el vector exacto que este
  guard vigila.

Refuerzos (write-side/contexto/adyacentes):

- 2608.06984 HarnessSafe (2026-08-07; cs.CR/cs.AI; benchmark de 328 casos en
  7 familias de carriers persistentes).
- 2606.26627 "Agents That Know Too Much" · 2601.06627 (Burn-After-Use +
  Secure Multi-Tenant) · 2605.01970 (Trojan Hippo) · 2608.01637 (Salami
  Attack) · 2606.17114 · 2605.08442 (inyecciones persistentes >97.5%) ·
  2606.00485 (Confused ChatGPT; 888 apps con contexto compartido).
- Write-side/contexto/taint: 2606.24322 · 2607.24625 (IFC/taint) ·
  2606.29279 (consolidación mem0/LangMem) · 2607.27080 (MemSecBench) ·
  2606.04141 · 2604.05432.
- Prior art propio: 2605.14421 (MemLineage — integridad write-time).

## 4. Hueco de estándar

OWASP Top 10 for Agentic Applications **2026** (ASI01-ASI10, lista verificada):
**no existe categoría de confidencialidad cross-principal**. ASI06 = Memory &
Context Poisoning (write-side). El contexto industrial (Claude Cowork,
ene-2026) confirma agentes multi-tenant con memoria compartida ya en
producción sin un sensor de confidencialidad estándar.

## 5. Veredicto

- Nicho validado **6/6** (checklist del método: problema real, mercado
  incipiente, no cubierto, abordable, ortogonal al prior art, distinguible).
- Ortogonalidad: memlineage = write-time/integridad; OWASP AMG = write-side;
  CrossSessionMemoryGuard = **read-time/confidencialidad** ("¿debería ESTE
  dato SALIR hacia ESTE principal?").

## 6. Evidencia cruda

- `/tmp/arxiv_xsession_out.txt` — barrido arXiv serial (6 queries, 31 KB).
- `/tmp/gh_gap_xsession_raw.txt` — salidas crudas `gh api`.
- `/tmp/harnesssafe_raw.xml` — XML crudo de 2608.06984 (3,155 bytes).
- Obsidian: `Nichos e Investigacion/CrossSessionMemoryGuard_Analysis_Nichos.md`,
  `CrossSessionMemoryGuard_Explicacion_Llana.md`, `Mapa_Nichos_Consolidado.md`.
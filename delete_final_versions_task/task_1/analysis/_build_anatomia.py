"""Genera ``anatomia_del_agente.ipynb``: qué entra, qué sale, los prompts y el diagrama.

    python delete_final_versions_task/task_1/analysis/_build_anatomia.py
    PYTHONPATH=src:. python delete_final_versions_task/task_1/analysis/_run_notebook.py \
        --notebook anatomia_del_agente.ipynb
"""

from __future__ import annotations

from delete_final_versions_task.task_1.agent.paths import LANGUAGE_MODEL, TEMPLATES, RUNS, ANATOMIA

from pathlib import Path

import nbformat as nbf

HERE = Path(__file__).resolve().parent
OUT = ANATOMIA
cells: list = []


def M(text: str) -> None:
    cells.append(nbf.v4.new_markdown_cell(text.strip("\n")))


def C(text: str) -> None:
    cells.append(nbf.v4.new_code_cell(text.strip("\n")))


# =========================================================================== #
M(r"""
# Anatomía del agente: qué entra, qué sale, qué se le dice al modelo

Este cuaderno abre la junta clínica por dentro sobre **un caso real** y la
sigue de principio a fin: los tres ficheros que entran, cómo se transforman en
las quince intervenciones, **qué prompt exacto vio el modelo de lenguaje en cada
turno y qué contestó**, qué tabla de variables construyó la sala, y los dos
ficheros que salen. Cierra con el diagrama de la arquitectura y con el análisis
agregado de las variables sobre los 195 casos.

Es el complemento de [`analisis_final.ipynb`](analisis_final.ipynb), que mide;
éste enseña. Los prompts se leen aquí tal como están en [`prompts.py`](../prompts.py),
con su análisis en [`PROMPTS.md`](../PROMPTS.md).
""")

C(r"""
import json, sys, re, warnings
from pathlib import Path
from collections import Counter, defaultdict

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

warnings.filterwarnings("ignore")
pd.set_option("display.width", 200); pd.set_option("display.max_columns", 40); pd.set_option("display.max_colwidth", 120)

REPO = Path.cwd()
while not (REPO / "src" / "chimera_agent_baseline").is_dir() and REPO != REPO.parent:
    REPO = REPO.parent
for p in (str(REPO), str(REPO / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from delete_final_versions_task.task_1.agent.paths import LANGUAGE_MODEL, TEMPLATES, RUNS, ANATOMIA
from delete_final_versions_task.task_1.agent.paths import TASK_ROOT, DATA
PKG = TASK_ROOT
from delete_final_versions_task.task_1.analysis import report as R
from delete_final_versions_task.task_1.agent import prompts as PR, protocol as P, decide as D
from delete_final_versions_task.common import roster as RO
from delete_final_versions_task.common.board import Board
from delete_final_versions_task.common import vocab as V

RUN = RUNS / "final"
run = R.load_run(RUN)
boards = R.load_boards(RUN)
gt, pay = R.ground_truth(), R.payloads()
S = {r["case_id"]: r for r in run["summary"] if r.get("ok")}

# El caso guía: uno etiquetado, con biopsia previa positiva (el cubo difícil) y
# con grado documentado en las notas, para que se vea el peldaño que lee documentos.
def _pick():
    for cid, r in S.items():
        if cid in gt and str(pay[cid].get("bx")) == "Positive" and r.get("grade") and cid in boards:
            return cid
    return next(iter(boards))
CASE = _pick()
b = boards[CASE]
print(f"corrida: {RUN.relative_to(REPO)} · {len(S)} casos entregados · caso guía: {CASE}")
print(f"  panel: PI-RADS {pay[CASE].get('pirads')} · PSA {pay[CASE].get('psa')} · PSAD {pay[CASE].get('psad')} · "
      f"edad {pay[CASE].get('age')} · biopsia previa {pay[CASE].get('bx')}")
print(f"  urólogo: {gt[CASE]['biopsy_decision']} — «{gt[CASE]['free_text'][:110]}»")
print(f"  entregado: {S[CASE]['decision']} · regla: {S[CASE]['protocol_rule']}")
""")

# --------------------------------------------------------------------------- #
M(r"""
---
# 1. La arquitectura

Una pizarra (Hearsay-II): un espacio común donde catorce participantes escriben
por turnos y nadie edita lo de otro. Tres tipos de participante, y el reparto es
la tesis de la solución:

* **código y expertos entrenados** (azul): leen el panel o los documentos ya
  abiertos y declaran, en el vocabulario del formulario, qué variables pesaron,
  a qué nivel y con qué confianza. Deciden el plan de documentos (Experto 4) y
  la decisión (protocolo);
* **modelo de lenguaje** (verde): recupera la guía, formula las preguntas, abre
  los documentos y reporta qué dicen, verifica, y redacta la nota clínica. **No
  vota**: sus votos se midieron en el azar en el cubo difícil;
* **herramientas MCP** (gris): los cinco documentos y la búsqueda en la guía.
  Lo que se abre es lo que se declara.
""")

C(r"""
fig, ax = plt.subplots(figsize=(15, 11.5))
ax.set_xlim(0, 15); ax.set_ylim(0, 11.5); ax.axis("off")
BLUE, GREEN, GREY, GOLD, RED = "#cfe0f5", "#d5ead9", "#e6e6e6", "#fbe7b2", "#f6d0cc"
EDGE = {"#cfe0f5": "#2b4c7e", "#d5ead9": "#2f6f4f", "#e6e6e6": "#555", "#fbe7b2": "#8a6d1a", "#f6d0cc": "#8b2e2e"}

def box(x, y, w, h, text, color, fs=8.6, bold_first=True):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12",
                                fc=color, ec=EDGE[color], lw=1.2))
    lines = text.split("\n")
    if bold_first:
        ax.text(x + w/2, y + h - 0.22, lines[0], ha="center", va="top", fontsize=fs+0.6, weight="bold", color=EDGE[color])
        rest = "\n".join(lines[1:])
        ax.text(x + w/2, y + h - 0.52, rest, ha="center", va="top", fontsize=fs, color="#222", linespacing=1.25)
    else:
        ax.text(x + w/2, y + h/2, text, ha="center", va="center", fontsize=fs, color="#222", linespacing=1.25)

def arrow(x1, y1, x2, y2, text=None, color="#444", style="-|>", ls="-"):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, mutation_scale=12, color=color, lw=1.1, ls=ls))
    if text:
        ax.text((x1+x2)/2, (y1+y2)/2 + 0.13, text, ha="center", va="bottom", fontsize=7.4, color=color)

# --- columna izquierda: entradas y artefactos ---------------------------------
box(0.2, 9.6, 3.0, 1.6, "ENTRADA · 3 ficheros por caso\nstructured-prompt.json (panel)\n*-clinical-data.json (EHR enmascarado)\nneural-representations.json", GREY, 8)
box(0.2, 7.3, 3.0, 1.9, "ARTEFACTOS ENTRENADOS\nE1 Extra-Trees · panel\nE2 proyector de PSA\nE3 Extra-Trees · panel+labs+RM\nE4 traza del urólogo\n+ 91 trazas etiquetadas (biblioteca)", BLUE, 8)
box(0.2, 5.2, 3.0, 1.7, "GUARDIAS (código)\nvalores sin fuente · grados sin fuente\nlenguaje de procedimiento · aterrizaje\nplan fijo · esquema Task1Output", RED, 8)
box(0.2, 3.0, 3.0, 1.8, "HERRAMIENTAS MCP\nget_mri_report · get_psa_trend\nget_previous_notes · get_lab_results\n(get_family_history: nunca)\nsearch_guidelines (gratis)", GREY, 8)

# --- columna central: las 15 intervenciones -------------------------------------
X, W = 4.0, 6.4
rows = [
    (10.55, "1-2  INTAKE", "el expediente, crudo y como lo ve el urólogo", GREY),
    (9.55, "3  EXPERT-STRUCTURED · E1", "bid + variables (not_used/noted/important/decisive) + confianza", BLUE),
    (8.75, "4  EXPERT-COHORT", "el criterio medido de la situación clínica, con sus variables", BLUE),
    (7.95, "5  EXPERT-LIBRARY", "3 precedentes etiquetados: qué pesó el urólogo en hombres parecidos", BLUE),
    (7.15, "6  EXPERT-TRACE · E4", "qué abre y qué pesa el urólogo aquí  →  FIJA EL PLAN", BLUE),
    (6.15, "7  EXPERT-EAU · LLM + RAG", "qué exige la guía, con cita; critica los niveles de los expertos", GREEN),
    (5.35, "8  MODERATOR · LLM", "preguntas abiertas por variable; una pregunta por documento", GREEN),
    (4.55, "10  REGISTRAR · LLM + MCP", "abre exactamente el plan; grado, sesiones, comparación, serie", GREEN),
    (3.55, "11-12  EXPERT-PSA · E2  /  EXPERT-FUSION · E3", "sólo sobre los documentos abiertos; variables y confianza", BLUE),
    (2.55, "13  PANEL-PROTOCOL", "cascada por acierto medido  →  DECIDE; tabla de variables de la sala", GOLD),
    (1.75, "14  VERIFIER · LLM + RAG", "¿decidible ya? pesos por variable; reabre sólo un documento del plan", GREEN),
    (0.75, "15  CHAIR · LLM", "parte clínico SIN locutores → la nota; firma el formulario", GREEN),
]
for y, head, sub, c in rows:
    box(X, y, W, 0.72, f"{head}\n{sub}", c, 8.2)
for i in range(len(rows) - 1):
    arrow(X + W/2, rows[i][0], X + W/2, rows[i+1][0] + 0.72)

# --- flechas de datos --------------------------------------------------------------
arrow(3.2, 10.4, X, 10.9, "panel", "#555")
arrow(3.2, 8.3, X, 9.9, "E1", "#2b4c7e"); arrow(3.2, 8.1, X, 7.5, "E4 + biblioteca", "#2b4c7e")
arrow(3.2, 7.6, X, 3.9, "E2 · E3", "#2b4c7e")
arrow(3.2, 3.9, X, 4.9, "documentos", "#555"); arrow(3.2, 3.5, X, 6.5, "guía", "#555", ls="--")
arrow(3.2, 6.0, X, 4.7, "", "#8b2e2e", ls=":"); arrow(3.2, 5.6, X, 1.1, "", "#8b2e2e", ls=":")
arrow(X + W, 2.0, 11.4, 5.7, "reabre (pase 2)", "#8a6d1a", ls="--")

# --- columna derecha: salidas y auditoría --------------------------------------
box(11.2, 8.4, 3.6, 2.2, "SALIDA · 2 ficheros por caso\nprostate-biopsy-decision.json\n  «yes» | «no»\nprostate-biopsy-decision-reasoning.json\n  confidence · variable_weights ·\n  reveal_sequence · free_text", GREY, 8)
box(11.2, 5.9, 3.6, 2.1, "DE DÓNDE SALE CADA CAMPO\ndecision → protocolo (13)\nconfidence · weights → E4 + acuerdo\nreveal_sequence → llamadas MCP reales\nfree_text → presidente (15), verificado", GOLD, 8)
box(11.2, 3.4, 3.6, 2.1, "TRAZA AUDITABLE\nacta JSON + Markdown (15 turnos)\nsummary.jsonl (decisión, regla, auditoría)\ntelemetry.jsonl (tokens, tiempo, herramientas)\npanel_cache.json (expertos)", GREY, 8)
arrow(X + W, 1.1, 11.2, 8.9, "", "#2f6f4f")
arrow(X + W, 2.9, 11.2, 6.9, "", "#8a6d1a")
ax.text(7.5, 11.35, "Junta clínica con expertos entrenados — tarea 1 (decisión de biopsia)", ha="center", fontsize=12, weight="bold")
ax.text(7.5, 11.05, "azul: código y expertos entrenados · verde: modelo de lenguaje · gris: datos y herramientas · dorado: decisión · rojo: guardias",
        ha="center", fontsize=8.2, color="#444")
plt.tight_layout(); plt.show()
""")

C(r"""
# El mismo grafo, tal como LangGraph lo compila: los nodos reales, con los bucles
# de herramientas del EAU, del registrador y del verificador y la reapertura.
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_mcp_adapters.client import MultiServerMCPClient
from delete_final_versions_task.task_1.agent.graph import create_conference_graph
from delete_final_versions_task.task_1.agent.run_task1 import mcp_args

class _Mute(BaseChatModel):
    @property
    def _llm_type(self): return "mute"
    def bind_tools(self, tools, **kw): return self
    def _generate(self, messages, stop=None, run_manager=None, **kw):
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="{}"))])

client = MultiServerMCPClient({"chimera": {"command": sys.executable, "args": mcp_args(), "transport": "stdio"}})
tools = await client.get_tools()
g = create_conference_graph(tools, _Mute(), None, None, None)
print("herramientas MCP servidas:", [t.name for t in tools])
lg = g.get_graph()
print(f"{len(lg.nodes)} nodos · {len(lg.edges)} aristas\n")
try:
    # grandalf falla en el trazado de aristas de grafos con varios bucles
    # («no intersection found»); si pasa, se lista el grafo en vez de dibujarlo.
    print(lg.draw_ascii())
except Exception as exc:
    print(f"(el trazado ASCII de grandalf falló: {type(exc).__name__}; se listan las aristas)\n")
    for e in lg.edges:
        tag = f"  [{e.data}]" if getattr(e, "data", None) else ""
        print(f"  {e.source:22} -> {e.target}{tag}")
""")

C(r"""
# Y en Mermaid, por si se lee en VS Code o JupyterLab, que lo renderizan.
print(g.get_graph().draw_mermaid())
""")

# --------------------------------------------------------------------------- #
M(r"""
---
# 2. Qué entra

Tres ficheros por caso. El agente ve **directamente** sólo el primero; el
segundo llega por herramientas MCP y sólo lo que el plan pide; el tercero lo
lee el experto de imagen, que en esta tarea mide en el azar y sólo habla si lo
convocan.
""")

C(r"""
case_dir = DATA / "agent_input" / CASE
prompt_json = json.loads((case_dir / "structured-prompt.json").read_text())
clinical = json.loads((case_dir / "prostate-biopsy-decision-clinical-data.json").read_text())
feats = json.loads((case_dir / "prostate-modality-level-neural-representations.json").read_text())
print("=== structured-prompt.json — el panel (campos escalares; las secciones de texto se recortan)")
for k, v in prompt_json.items():
    if isinstance(v, (str, int, float)) and k not in ("notes",):
        print(f"   {k:20} {str(v)[:90]}")
print(f"   note_sections        {len(prompt_json.get('note_sections') or [])} apartados de la nota de encuentro")
print(f"\n=== prostate-biopsy-decision-clinical-data.json — el EHR extendido, enmascarado tras las herramientas")
for k, v in clinical.items():
    body = json.dumps(v, ensure_ascii=False)
    print(f"   {k:20} {len(body):6} caracteres   {body[:80]}…")
print(f"\n=== prostate-modality-level-neural-representations.json")
for k, v in feats.items():
    if isinstance(v, list):
        print(f"   {k:20} {len(v)} vector(es) de dimensión {len(v[0]) if v and isinstance(v[0], list) else '?'}")
""")

C(r"""
# Lo que el urólogo lector ve antes de abrir nada — y lo que INTAKE lee en voz alta
# como intervención 2 — es el panel renderizado con la plantilla upstream.
from chimera_agent_baseline.case_loader import render_baseline_prompt
print(render_baseline_prompt(prompt_json, TEMPLATES))
""")

C(r"""
# Qué reciben los expertos entrenados de ese mismo caso: el panel precalculado.
from delete_final_versions_task.task_1.experts_1.panel import CACHE, Panel
panel = Panel(CACHE)
v = panel.verdicts(CASE, "deployed")
print("veredictos de los expertos para el caso guía (artefactos entrenados con los 91):")
for name in ("structured", "fusion_full", "fusion_nolab"):
    x = v[name]
    print(f"   {name:13} {x['decision']:3}  p={x['p']:.2f} ±{x['sigma']:.2f}  tramo={x['tier']:8} confianza={x['confidence']}")
print(f"   trace         abre {v['trace']['reveal_sequence']} · confianza {v['trace']['confidence']}")
print(f"   psa           {panel.projection(CASE)['direction']} ({panel.projection(CASE)['direction_confidence']})")
print("\nvariables que cada clasificador declara, en el vocabulario del formulario (importancia de permutación out-of-fold):")
for name in ("structured", "fusion"):
    w = panel.experts[name]["form_weights"]; sh = panel.experts[name]["variable_importance_share"]
    print(f"   {name:11} " + " · ".join(f"{k}={w[k]} ({sh[k]:.0%})" for k in V.VARIABLES_BY_TASK[1] if w[k] != "not_used"))
""")

# --------------------------------------------------------------------------- #
M(r"""
---
# 3. La sesión, turno a turno

Las quince intervenciones del caso guía. Para cada turno del modelo de lenguaje
se muestra **el prompt de sistema** (lo que define el papel), **el prompt de
usuario que vio en ese momento** (reconstruido desde el acta persistida, que es
exactamente lo que se le pasó) y **lo que contestó**. Para los turnos de código
se muestra lo que escribieron.
""")

C(r"""
from transformers import AutoTokenizer
tok = AutoTokenizer.from_pretrained(str(LANGUAGE_MODEL))
ntok = lambda t: len(tok.encode(t, add_special_tokens=False))

def upto(n):
    # el acta tal como estaba justo antes de la intervención n
    return Board.from_dicts(CASE, 1, [i for i in b["interventions"] if i["n"] < n])

def show(title, text, limit=None):
    print("=" * 100); print(title); print("=" * 100)
    print(text if limit is None else text[:limit] + ("\n[…]" if len(text) > limit else "")); print()

items = {i["n"]: i for i in b["interventions"]}
by_speaker = defaultdict(list)
for i in b["interventions"]:
    by_speaker[i["speaker"]].append(i)
print(f"{b['n_interventions']} intervenciones; el acta completa pesa {ntok(Board.from_dicts(CASE, 1, b['interventions']).render()):,} tokens")
for i in b["interventions"]:
    print(f"  [{i['n']:2}] {i['speaker']:18} {ntok(i['body']):5} tokens · {(i.get('data') or {}).get('gist', '')[:80]}")
""")

C(r"""
# 1-6: los turnos de código y de los expertos entrenados, íntegros.
for n in range(1, 7):
    it = items[n]
    show(f"INTERVENCIÓN {n} · {it['speaker']}", it["body"], limit=2600 if n <= 2 else None)
""")

C(r"""
# 7 · EXPERT-EAU: el prompt de sistema, el prompt de usuario que vio, y su respuesta.
it = by_speaker["EXPERT-EAU"][0]
show(f"EXPERT-EAU · prompt de SISTEMA ({ntok(PR.EAU_SYSTEM):,} tokens)", PR.EAU_SYSTEM)
user = PR.eau_user(upto(it["n"]).render())
show(f"EXPERT-EAU · prompt de USUARIO ({ntok(user):,} tokens) — el acta hasta la intervención {it['n']-1} más la consigna; se muestra el final",
     user[-1500:])
show("EXPERT-EAU · RESPUESTA", it["body"])
""")

C(r"""
# 8 · MODERATOR
it = by_speaker["MODERATOR"][0]
show(f"MODERATOR · prompt de SISTEMA ({ntok(PR.moderator_system('<catálogo>')):,} tokens)", PR.moderator_system("<el catálogo de documentos, generado desde la lista MCP viva>"))
planned = S[CASE].get("planned") or []
user = PR.moderator_user(upto(it["n"]).render(), 1, planned, [], None)
show(f"MODERATOR · prompt de USUARIO — sólo la consigna final (el acta va delante)", user[-900:])
show("MODERATOR · RESPUESTA (ya convertida en plan por el código)", it["body"])
""")

C(r"""
# 10 · REGISTRAR: abre el plan y reporta. Su prompt de usuario lleva las preguntas del moderador.
it = by_speaker["REGISTRAR"][0]
show(f"REGISTRAR · prompt de SISTEMA ({ntok(PR.REGISTRAR_SYSTEM):,} tokens)", PR.REGISTRAR_SYSTEM)
plan = (by_speaker["MODERATOR"][0].get("data") or {}).get("plan") or []
show("REGISTRAR · prompt de USUARIO — la consigna con el plan (el acta va delante)", PR.registrar_user("", plan, 1))
show(f"REGISTRAR · RESPUESTA — abrió {it['data'].get('revealed')}", it["body"])
tele = [t for t in run["telemetry"] if t.get("kind") == "tool" and t.get("case_id") == CASE]
print("herramientas llamadas en este caso:", [(t["tool"], f"{t['seconds']}s", f"{t['tokens']} tok") for t in tele])
""")

C(r"""
# 11-13: los expertos que leen documentos, y el protocolo con la tabla de variables de la sala.
for sp in ("EXPERT-PSA", "EXPERT-FUSION", "PANEL-PROTOCOL"):
    for it in by_speaker.get(sp, []):
        show(f"INTERVENCIÓN {it['n']} · {sp}", it["body"])
""")

C(r"""
# 14 · VERIFIER
it = by_speaker["VERIFIER"][0]
show(f"VERIFIER · prompt de SISTEMA ({ntok(PR.VERIFIER_SYSTEM):,} tokens)", PR.VERIFIER_SYSTEM)
qs = S[CASE].get("questions") or []
opened = S[CASE]["reveal_sequence"]
show("VERIFIER · prompt de USUARIO — la consigna (el acta va delante)",
     PR.verifier_user("", qs, opened, [s for s in planned if s not in opened], 1, 2))
show("VERIFIER · RESPUESTA", it["body"])
""")

C(r"""
# 15 · CHAIR: NO ve el acta. Ve el parte clínico, reconstruido aquí desde el acta persistida.
it = by_speaker["CHAIR"][0]
show(f"CHAIR · prompt de SISTEMA ({ntok(PR.CHAIR_SYSTEM):,} tokens) — sin lista de participantes", PR.CHAIR_SYSTEM)
proto = by_speaker["PANEL-PROTOCOL"][-1]["data"]
reg_body = by_speaker["REGISTRAR"][-1]["body"]
grade = {"gg": S[CASE].get("grade"), "quote": S[CASE].get("grade_quote"), "on_surveillance": S[CASE].get("on_surveillance")}
because, against, alternative = P.clinical_reason(pay[CASE], grade, opened, proto["decision"])
found = re.split(r"WHAT I DID NOT OPEN|WHAT THIS SUPPORTS|WHERE THIS LEANS", reg_body.split("WHAT I FOUND", 1)[-1])[0].strip()
corpus = "\n".join(json.dumps(clinical[s], ensure_ascii=False) for s in opened if s in clinical)
found, _ = D.drop_unsourced_grade_lines(found, corpus)
eau_body = by_speaker["EXPERT-EAU"][0]["body"]
guideline = re.split(r"WHAT THE EXPERTS", eau_body.split("GUIDELINE", 1)[-1])[0].strip()
digest = PR.clinical_digest(pay[CASE], opened, found, grade, guideline, because, against, proto["decision"],
                            proto["confidence"], proto["variable_weights"], alternative, proto.get("variable_view"))
print(f"[el parte pesa {ntok(digest):,} tokens; el acta completa, {ntok(Board.from_dicts(CASE, 1, b['interventions']).render()):,}]\n")
from chimera_agent_baseline.output.schema import eligible_variables
elig = eligible_variables(1, set(RO.TOOL_BY_SECTION[s] for s in opened if s in RO.TOOL_BY_SECTION))
user = PR.chair_user(CASE, digest, pay[CASE], elig, PR.chair_skeleton(elig))
show(f"CHAIR · prompt de USUARIO ({ntok(user):,} tokens) — el parte clínico, el marco, tres notas reales del urólogo y el esqueleto", user)
show("CHAIR · RESPUESTA (turno en el acta)", it["body"])
print("auditoría del turno:", json.dumps(it["data"].get("audit"), ensure_ascii=False))
""")

# --------------------------------------------------------------------------- #
M(r"""
---
# 4. Qué sale

Dos ficheros, con el esquema del reto, y una traza. Abajo, el registro
entregado y la comparación con el urólogo lector.
""")

C(r"""
out_dir = RUN / "output" / "task1" / CASE
dec = json.loads((out_dir / "prostate-biopsy-decision.json").read_text())
rea = json.loads((out_dir / "prostate-biopsy-decision-reasoning.json").read_text())
print("=== prostate-biopsy-decision.json"); print(json.dumps(dec))
print("\n=== prostate-biopsy-decision-reasoning.json"); print(json.dumps(rea, indent=2, ensure_ascii=False))
from chimera_agent_baseline.output.schema import Task1Output
Task1Output(case_id=CASE, task=1, biopsy_decision=dec == "yes", confidence=rea["confidence"],
            variable_weights=rea["variable_weights"], reveal_sequence=rea["reveal_sequence"], reasoning=rea["free_text"])
print("\nvalida contra Task1Output: sí")
print(f"\n=== el urólogo lector, mismo caso\n   decisión: {gt[CASE]['biopsy_decision']} · confianza: {gt[CASE]['confidence']}")
print(f"   pesos: {gt[CASE]['variable_weights']}\n   abrió: {gt[CASE]['reveal_sequence']}\n   escribió: «{gt[CASE]['free_text']}»")
ev = R.evaluator()
row = ev.evaluate_case({**gt[CASE]}, {**rea, "biopsy_decision": dec, "case_id": CASE}, None, None)
print(f"\n=== puntuación oficial de este caso: case_score {row['case_score']:.3f} · "
      + " · ".join(f"{k.replace('_score','')} {row[k]:.2f}" for k in R.COMPONENTS if row.get(k) is not None))
""")

C(r"""
# Coste de este caso, por papel: lo que la telemetría midió con el tokenizador del modelo.
llm = pd.DataFrame([t for t in run["telemetry"] if t.get("kind") == "llm" and t.get("case_id") == CASE])
display(llm.groupby("role").agg(llamadas=("role", "size"), tokens_entrada=("prompt_tokens", "sum"),
                                 tokens_salida=("completion_tokens", "sum"), segundos=("seconds", "sum")).round(2))
print(f"total: {S[CASE]['seconds']} s · {S[CASE]['tel_prompt_tokens']:,} tokens de entrada · {S[CASE]['tel_completion_tokens']:,} de salida")
""")

# --------------------------------------------------------------------------- #
M(r"""
---
# 5. Las variables de la sala, sobre los 195 casos

Cada experto declara sus variables en el vocabulario del formulario. Aquí se
mide, sobre los 91 casos etiquetados, **cuánto se parece cada experto al
urólogo** en lo que marca como *important* o *decisive*, y cómo se reparte el
acuerdo del panel. Es el análisis que sostiene una decisión de diseño: subir
al formulario los pesos por acuerdo del panel **baja** la nota (0.8390 → 0.8365
medido), así que los pesos que se entregan siguen siendo los del Experto 4 y las
variables de los demás alimentan el razonamiento, no el formulario.
""")

C(r"""
EXPERTS = ["EXPERT-STRUCTURED", "EXPERT-FUSION", "EXPERT-COHORT", "EXPERT-LIBRARY", "EXPERT-PSA"]
STRONG = ("important", "decisive")
rows = []
for cid, r in S.items():
    if cid not in gt or not r.get("variable_view"):
        continue
    for vv in r["variable_view"]:
        var = vv["variable"]
        g = gt[cid]["variable_weights"].get(var)
        rows.append({"case": cid, "variable": var, "urólogo": g in STRONG, "entregado": vv["record"] in STRONG,
                     "trace": vv["trace"] in STRONG,
                     **{e: (vv["levels"].get(e) in STRONG) for e in EXPERTS if e in vv["levels"]}})
df = pd.DataFrame(rows)
cols = [c for c in ["entregado", "trace"] + EXPERTS if c in df]
agree = df.groupby("variable")[cols + ["urólogo"]].mean().round(2)
print("fracción de casos etiquetados en que cada fuente marca la variable important/decisive (urólogo = referencia):")
display(agree)
match = pd.DataFrame({c: (df[c] == df["urólogo"]).groupby(df["variable"]).mean() for c in cols}).round(2)
print("\nacuerdo con el urólogo (misma clase important/decisive vs resto), por variable y fuente:")
display(match)
print("\nacuerdo medio con el urólogo:", match.mean().round(3).to_dict())
""")

C(r"""
fig, ax = plt.subplots(figsize=(10, 4))
m = match.T
im = ax.imshow(m.values, cmap="Greens", vmin=0.4, vmax=1.0, aspect="auto")
ax.set_xticks(range(len(m.columns))); ax.set_xticklabels(m.columns, rotation=0)
ax.set_yticks(range(len(m.index))); ax.set_yticklabels([i.replace("EXPERT-", "") for i in m.index])
for i in range(m.shape[0]):
    for j in range(m.shape[1]):
        ax.text(j, i, f"{m.values[i, j]:.2f}", ha="center", va="center", fontsize=8, color="#111")
ax.set_title("Acuerdo con el urólogo en marcar cada variable important/decisive (91 casos etiquetados)")
plt.colorbar(im, ax=ax, fraction=0.025); plt.tight_layout(); plt.show()
print("Lectura: el Experto 4 (trace) y lo entregado siguen al urólogo; los clasificadores discrepan en `bx` y")
print("`comorbidity` porque miden lo que MOVIÓ su predicción, no lo que un urólogo marcaría. Es la divergencia")
print("que la sala ve en cada acta, y la razón de que sus pesos no vayan al formulario.")
""")

C(r"""
# La confianza que declara cada experto, frente a la del urólogo y a la entregada.
CM = {"clear": 2, "borderline": 1, "uncertain": 0}
rows = []
for cid, r in S.items():
    if cid not in gt or not r.get("expert_confidence"):
        continue
    for who, c in r["expert_confidence"].items():
        if c in CM:
            rows.append({"quién": who.replace("EXPERT-", ""), "distancia": abs(CM[c] - CM[gt[cid]["confidence"]]) / 2})
    rows.append({"quién": "ENTREGADO", "distancia": abs(CM[r["confidence"]] - CM[gt[cid]["confidence"]]) / 2})
cdf = pd.DataFrame(rows)
tab = (1 - cdf.groupby("quién")["distancia"].mean()).sort_values(ascending=False).round(3).rename("confidence_score que obtendría")
display(tab.to_frame())
print("Es el mismo cálculo que hace el evaluador oficial (1 − distancia ordinal / 2). La confianza entregada")
print("sale del acuerdo entre expertos y del tramo del que hablan, y es la que mejor sigue al urólogo.")
""")

C(r"""
# ¿La nota nombra las variables que el formulario registra como motores? Es la
# coherencia entre las dos mitades de la salida, y la razón de que el presidente
# reciba una lista corta y no la tabla entera: con la tabla delante bajaba.
PAT = {"pirads": r"PI-?RADS|\bP[2-5]\b", "psa": r"\bPSA\b(?!\s*densit|D)", "psad": r"PSAD|PSA densit",
       "bx": r"prior (positive |negative )?biops|biopsy-naive|ISUP|Gleason|surveillance",
       "age": r"\b\d{2}\s*(y|yo|y/o|-year)", "vol": r"volume|\bmL\b(?!/)", "dre": r"\bDRE\b|nodul|palpab",
       "comorbidity": r"comorbid|IPSS|LUTS", "cspca": r"csPCa", "fh": r"family histor"}
def prf(recs):
    rec, pre = [], []
    for r in recs:
        strong = {k for k, v in (r.get("variable_weights") or {}).items() if v in ("important", "decisive")}
        named = {k for k, pat in PAT.items() if re.search(pat, r.get("free_text") or "", re.I)}
        if strong:
            rec.append(len(strong & named) / len(strong))
        if named:
            pre.append(len(strong & named) / len(named))
    r_, p_ = float(np.mean(rec)), float(np.mean(pre))
    return {"recall": round(r_, 3), "precisión": round(p_, 3), "F1": round(2 * r_ * p_ / (r_ + p_), 3)}

filas = []
for label, root in (("nada (esta versión)", RUN),
                    ("la tabla entera", RUNS / "_v2_tabla_en_el_parte"),
                    ("sólo la lista de variables", RUNS / "_v3_lista_en_el_parte")):
    if (root / "summary.jsonl").exists():
        filas.append({"qué ve el presidente de la tabla": label,
                      **prf([r for r in R.load_run(root)["summary"] if r.get("ok")])})
display(pd.DataFrame(filas).set_index("qué ve el presidente de la tabla"))
print("Cuántas de las variables que el formulario registra como motores llega a nombrar la nota (recall), y")
print("cuántas de las que nombra están de verdad registradas (precisión). Las tres configuraciones dan la")
print("MISMA nota oficial —0.8390— porque el juez de razonamiento está apagado; lo que cambia es la nota.")
print("La dirección es consistente y contraintuitiva: darle al presidente la lista de variables no le ayuda")
print("a nombrarlas. La tabla vive en el acta y en el turno del verificador, que sí la usan.")
""")

C(r"""
# Cuántas variables pone la sala sobre la mesa, frente a las que el urólogo marca.
n_room = [sum(1 for vv in r["variable_view"] if vv["n_strong"] > 0) for r in S.values() if r.get("variable_view")]
n_uro = [sum(1 for v in g["variable_weights"].values() if v in STRONG) for g in gt.values()]
n_out = [sum(1 for v in r["variable_weights"].values() if v in STRONG) for r in S.values()]
print(f"variables marcadas important/decisive por AL MENOS un experto, por caso: media {np.mean(n_room):.1f}")
print(f"variables important/decisive en el formulario entregado, por caso:        media {np.mean(n_out):.1f}")
print(f"variables important/decisive que marca el urólogo, por caso:              media {np.mean(n_uro):.1f}")
print("\nLa sala discute más variables de las que se entregan; el formulario se ciñe a lo que el urólogo marca,")
print("que es lo que el evaluador compara.")
""")

# --------------------------------------------------------------------------- #
M(r"""
---
# 6. Los prompts, en cifras

Cada prompt de sistema con su coste y su cota. El análisis de cada uno —qué se
midió que hacía mal y qué se cambió— está en [`PROMPTS.md`](../PROMPTS.md).
""")

C(r"""
filas = [("cabecera común (la ven EAU, moderador, registrador, verificador)", PR.CONFERENCE, "—"),
         ("EXPERT-EAU", PR.EAU_SYSTEM, "200 palabras; 1 búsqueda; una línea por documento"),
         ("MODERATOR", PR.MODERATOR_SYSTEM, "un JSON; preguntas por variable"),
         ("REGISTRAR", PR.REGISTRAR_SYSTEM, "320 palabras; llamar antes de escribir; líneas obligatorias"),
         ("VERIFIER", PR.VERIFIER_SYSTEM, "280 palabras; pesos por variable; línea VERDICT"),
         ("CHAIR", PR.CHAIR_SYSTEM, "40-90 palabras; sin acta ni nombres; lista negra")]
display(pd.DataFrame([{"prompt": a, "tokens": ntok(t), "palabras": len(t.split()), "cota": c} for a, t, c in filas]).set_index("prompt"))
print("Lo que el modelo ve por caso (media de la corrida):")
llm_all = pd.DataFrame([t for t in run["telemetry"] if t.get("kind") == "llm"])
n_cases = llm_all["case_id"].nunique()
display((llm_all.groupby("role")[["prompt_tokens", "completion_tokens"]].sum() / n_cases).round(0).astype(int)
        .rename(columns={"prompt_tokens": "tokens de entrada / caso", "completion_tokens": "tokens de salida / caso"}))
""")

nb = nbf.v4.new_notebook(cells=cells)
nb.metadata["kernelspec"] = {"display_name": "chimera-baseline", "language": "python", "name": "chimera-baseline"}
nb.metadata["language_info"] = {"name": "python"}
OUT.write_text(nbf.writes(nb))
print(f"escrito {OUT} ({len(cells)} celdas)")

"""Experto #1 — el recomendador inicial (kNN probabilístico con A ± ΔA).

Es el primer participante que escribe después del caso. Su papel es
deliberadamente modesto: **abrir la discusión con un número**, no cerrarla. El
módulo entrenado vive en ``delete_solution_one/recomendador_inicial`` y sólo
lee ``structured-prompt.json`` — ni historia clínica ni embeddings — así que
no consume presupuesto de revelación (``tool_score`` del evaluador es
precisión sobre las secciones reveladas, y este experto no revela ninguna).

Lo que aporta que un LLM no puede aportar solo:

* una probabilidad calibrada out-of-fold (AUC 0.75, ECE 0.095 en 5x5 CV);
* una barra de error que **separa** la duda por desacuerdo entre vecinos
  (aleatoria) de la duda por falta de casos parecidos (epistémica);
* un tramo operativo medido, no supuesto: en validación el tramo ``firme``
  no falló ninguno de sus casos, y el tramo ``discutir`` acierta apenas más
  que la clase mayoritaria. Esa autocrítica es lo que se escribe en la pizarra.

Si el artefacto no está en disco, el experto escribe que no puede opinar y la
pizarra sigue: ningún caso se pierde por esto.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

#: Directorio del módulo entrenado (hermano de este paquete).
RECOMMENDER_DIR = Path(__file__).resolve().parents[2] / "recomendador_inicial"

#: Frase que el reto/el diseño exige que acompañe siempre a la sugerencia: deja
#: explícito que esto es un punto de partida para discutir, no un dictamen.
DISCLAIMER = (
    "A basic classifier, whose sole purpose is to provide a suggestion, produces this "
    "result along with its associated uncertainty. The purpose of this decision is to "
    "use it as an initial reference point for discussing the results."
)

_TIER_GUIDANCE = {
    "firme": (
        "TIER 'firm': A +/- 1.96*dA does not cross the 0.5 threshold. On the 91 labelled "
        "cases this tier was never wrong, but it only covered 17 of them, so the 95% CI "
        "on that accuracy still reaches down to ~0.75. Treat it as a strong prior that "
        "should only be overturned by explicit contradicting evidence."
    ),
    "apoya": (
        "TIER 'supports': A +/- dA does not cross 0.5, but A +/- 1.96*dA does. There is a "
        "direction, not a conclusion. Measured accuracy in this tier: 0.67. Treat it as a "
        "weighted vote, not as a decision."
    ),
    "discutir": (
        "TIER 'discuss': A +/- dA straddles 0.5. The classifier genuinely CANNOT tell these "
        "two answers apart; measured accuracy in this tier is 0.61, barely above the 0.62 "
        "majority-class rate. Its number is a starting point only, and the case must be "
        "decided on the clinical evidence retrieved by the other participants."
    ),
}

_ROLE = (
    "statistical expert; k-NN over 8 structured variables of THIS prompt only, "
    "trained on 91 labelled cases, leave-one-out honest"
)

_recommender: Any = None


def _load_recommender():
    global _recommender
    if _recommender is None:
        if str(RECOMMENDER_DIR) not in sys.path:
            sys.path.insert(0, str(RECOMMENDER_DIR))
        from entrenar_recomendador_inicial import RecomendadorInicial  # noqa: PLC0415

        _recommender = RecomendadorInicial.cargar()
        log.info("Recomendador inicial cargado desde %s", RECOMMENDER_DIR)
    return _recommender


def suggest(prompt_payload: dict[str, Any]) -> dict[str, Any]:
    """Devuelve la salida cruda del recomendador (o un dict de error)."""
    try:
        return _load_recommender().recomendar(prompt=prompt_payload)
    except Exception as exc:  # noqa: BLE001 — la pizarra debe seguir aunque esto falle
        log.warning("Recomendador inicial no disponible: %s", exc)
        return {"error": f"{type(exc).__name__}: {exc}"}


def render(prompt_payload: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    """(role, body, data) listos para escribir en la pizarra."""
    out = suggest(prompt_payload)
    if "error" in out:
        body = (
            "The initial statistical recommender is unavailable for this case "
            f"({out['error']}). No prior probability is contributed; decide on the "
            "clinical evidence alone."
        )
        return _ROLE, body, out

    unc = out["incertidumbre"]
    tier = out["veredicto_operativo"]
    used = ", ".join(f"{k}={v}" for k, v in out["variables_usadas"].items() if v is not None)
    missing = ", ".join(out["variables_faltantes"]) or "none"
    ic95 = f'{out["intervalo_95"][0]:.2f}-{out["intervalo_95"][1]:.2f}'
    neighbours = out.get("evidencia", [])
    n_yes = sum(1 for n in neighbours if n["decision"] == "yes")

    body = f"""{DISCLAIMER}

SUGGESTION: {"BIOPSY" if out["prediccion"] == "yes" else "NO BIOPSY"}
  p(biopsy = yes) = {out["A"]:.2f} +/- {out["delta_A"]:.2f}   (95% CI {ic95})

Where the uncertainty comes from:
  - aleatoric  dA = {unc["delta_aleatoria"]:.2f}  (the nearest labelled cases disagree with each other)
  - epistemic  dA = {unc["delta_epistemica"]:.2f}  (few labelled cases resemble this one)
  - {unc["vecinos_efectivos"]:.1f} effective neighbours out of {unc["de_k_vecinos"]}; \
{n_yes} of the {len(neighbours)} closest labelled cases were biopsied
  - 80%-coverage conformal set: {{{", ".join(unc["conjunto_conformal"])}}}

{_TIER_GUIDANCE.get(tier, "")}

Variables it actually read (from the visible panel only, no documents retrieved):
  {used}
  missing / not evaluable: {missing}

Out-of-fold performance of this recommender on the 91 labelled cases (5x5 CV):
  accuracy {out["rendimiento_validacion"]["acc"]}, balanced accuracy \
{out["rendimiento_validacion"]["bal_acc"]}, AUC {out["rendimiento_validacion"]["auc"]}, \
ECE {out["rendimiento_validacion"]["ece"]}.
It is right about 7 times out of 10 overall. It is NOT an oracle and it has never seen the
radiology report, the PSA trajectory, the laboratory panel or the previous notes."""

    return _ROLE, body, out

"""Bloque D — extracción de hallazgos del informe radiológico en texto libre.

El informe de RM multiparamétrica del corpus es una paráfrasis en lenguaje
natural de una plantilla PI-RADS v2.1: cada informe describe, con vocabulario
variable, el mismo conjunto de hallazgos (zona, tamaño, señal T2, restricción
en difusión, realce dinámico, extensión extracapsular, invasión de vesículas
seminales, adenopatías, lesiones óseas). Ese texto contiene información que
**no** está en ``structured-prompt.json``: el tamaño de la lesión, su zona y el
estadio local radiológico.

La extracción usa el algoritmo **NegEx** (Chapman, Bridewell, Hanbury, Cooper y
Buchanan, *J Biomed Inform* 2001): se localiza el concepto dentro de una
oración y se busca en esa misma oración una señal de negación en la ventana
sintáctica adecuada (pre-negación antes del concepto, post-negación después).
Es un método determinista, auditable y sin entrenamiento, que es exactamente lo
que hace falta cuando el corpus tiene 91 casos etiquetados y no se puede
permitir gastar datos en aprender a leer.

Cada concepto devuelve un valor **ternario**: 1.0 afirmado, 0.0 negado, NaN no
mencionado. Distinguir "negado" de "no mencionado" es esencial: un informe que
dice "sin extensión extracapsular" es evidencia; uno que no la menciona, no.
"""

from __future__ import annotations

import math
import re

NAN = float("nan")

# --------------------------------------------------------------------------
# Léxico de conceptos. Cada entrada es una lista de patrones alternativos.
# --------------------------------------------------------------------------

CONCEPTS: dict[str, str] = {
    "dwi_restriction": r"(restrict\w*\s+(diffusion|movement|water)|diffusion\s+restrict\w*|restriction)",
    "adc_low": r"(low\s+adc|adc\s+(signal\s+)?(is\s+)?(low|dark|depressed|reduced|diminished)|dark\s+adc|hypointens\w*\s+on\s+adc|drop\s+on\s+the\s+adc|hypointensity\s+on\s+adc)",
    "dce_early_focal": r"(earl\w*[,\s]+(and\s+)?(focal|localis\w*|localiz\w*)\s+(enhance\w*|uptake)|(focal|localis\w*|localiz\w*)\s+earl\w*\s+enhance\w*|(prompt|rapid|brisk)\w*[,\s]+(focal|localis\w*|localiz\w*)\s+enhance\w*|avid\s+enhance\w*|hyperenhanc\w*|early\s+enhance\w*)",
    "epe": r"(extracapsular\s+(extension|spread)|extraprostatic\s+(extension|spread)|capsular\s+(breach|disruption|involvement|integrity))",
    "svi": r"(seminal\s+vesicle\s+(invasion|involvement|infiltration))",
    "lymphadenopathy": r"(lymphadenopathy|lymph\s+node\w*|nodal\s+(enlargement|disease))",
    "bone_lesion": r"(osseous\s+(lesion|metastas\w*|change|abnormalit\w*)|bone\s+(metastas\w*|lesion)|sclerotic\s+(lesion|focus)|skeleton)",
    "t2_marked_hypo": r"((marked\w*|pronounced\w*|profound\w*|intense\w*|strong\w*)\s+(t2\s+)?hypointens\w*|homogeneously\s+hypointens\w*)",
    "ill_defined": r"(ill[-\s]defined|poorly\s+(circumscribed|defined|marginated)|indistinct\s+(margin|border)|infiltrativ\w*)",
    "bph_nodularity": r"(benign\s+(nodular\s+)?(prostatic\s+)?hyperplasia|bph|adenomatous\s+nodul\w*|nodular\s+hyperplasia)",
    "prior_treatment_change": r"(post[-\s]?(radiation|radiotherapy|treatment)|hormonal\s+(therapy|deprivation)|post[-\s]?biopsy\s+h(a)?emorrhag\w*)",
}

#: Un hallazgo negado en algunos de estos conceptos es en sí mismo informativo.
TERNARY_CONCEPTS = tuple(CONCEPTS)

# --------------------------------------------------------------------------
# NegEx: señales de negación y terminadores de ámbito.
# --------------------------------------------------------------------------

#: Pseudo-negaciones: contienen una señal de negación pero no niegan nada.
PSEUDO_NEGATIONS = [
    r"not\s+only",
    r"no\s+(change|increase|significant\s+change)\s+in\s+size",
    r"cannot\s+be\s+excluded",
    r"not\s+excluded",
    r"not\s+definitively\s+excluded",
]

#: Señales de pre-negación: niegan lo que viene *después* en la oración.
PRE_NEGATIONS = [
    r"\bno\b", r"\bwithout\b", r"\bnegative\b", r"\bfree\s+of\b", r"\bclear\s+of\b",
    r"\babsence\s+of\b", r"\babsent\b", r"\bnot\b", r"\bneither\b", r"\bnor\b",
    r"\bunremarkable\b", r"\blacks?\b", r"\blacking\b", r"\bdevoid\s+of\b",
    r"\brules?\s+out\b", r"\bruled\s+out\b", r"\bexclud\w+\b",
]

# --------------------------------------------------------------------------
# Post-negación. El informe radiológico coloca la negación *después* del
# hallazgo con mucha más frecuencia que la nota clínica para la que se diseñó
# NegEx ("los ganglios pélvicos no muestran adenopatías"), de modo que esta
# parte del léxico es deliberadamente más rica que la del artículo original.
# Se construye por composición de tres grupos en lugar de enumerar frases, para
# que la cobertura no dependa del vocabulario concreto del corpus.
# --------------------------------------------------------------------------

#: Verbos de reporte / cópulas que introducen el estado del hallazgo.
_REPORT_VERB = (
    r"(?:is|are|was|were|appears?|appeared|remains?|remained|maintains?|maintained|retains?|retained|"
    r"stays?|holds?|continues?|shows?|showed|demonstrates?|demonstrated|reveals?|revealed|"
    r"displays?|displayed|exhibits?|exhibited|discloses?|disclosed|measures?|measured|comes?\s+back)"
)

#: Adjetivos / sustantivos que significan "no hay hallazgo".
_ABSENT_ADJ = (
    r"(?:absent|unremarkable|normal|benign|negative|preserved|intact|inconspicuous|symmetric|"
    r"unobserved|undetected|unidentified|unseen|clear|non[-\s]?enlarged|sub[-\s]?centimet\w*|"
    r"within\s+normal\s+limits)"
)

#: Sustantivos de propiedad que suelen acompañar a "normal" ("normal size and
#: contour"), y que por tanto extienden el ámbito de la negación.
_PROPERTY_NOUN = r"(?:size|sizing|dimensions?|signal|calibre|caliber|structure|architecture|morphology|contour|appearance)"

POST_NEGATIONS = [
    # "... are (conspicuously) absent / appear benign / remain unremarkable"
    rf"\b{_REPORT_VERB}\s+(?:\w+ly\s+)?{_ABSENT_ADJ}\b",
    # "... show normal size and contour / retain normal architecture"
    rf"\b{_REPORT_VERB}\s+(?:\w+ly\s+)?(?:normal|preserved|unremarkable)?\s*{_PROPERTY_NOUN}\b",
    # "... show no / demonstrate none / come back without"
    rf"\b{_REPORT_VERB}\s+(?:no|none|without|clear\s+of|free\s+of)\b",
    # "... is not identified / was never detected"
    r"\b(?:not|never)\s+(?:identified|observed|detected|seen|present|appreciated|evident|visualiz\w+|"
    r"visualis\w+|demonstrated|noted|apparent|found|reported|described)\b",
    r"\b(?:is|are|was|were)\s+not\b",
    # "... lacks suspicious changes / is devoid of"
    r"\b(?:lacks?|lacking|devoid\s+of|free\s+of|clear\s+of|spared|uninvolved)\b",
    # giros idiomáticos de ausencia
    r"\bby\s+its\s+absence\b", r"\bconspicuous\s+only\b", r"\bwithin\s+normal\s+limits\b",
]

#: Frases que, para un concepto concreto, son evidencia positiva de ausencia
#: aunque el patrón general no las capture. Se evalúan antes que NegEx y fijan
#: el concepto a 0.0 (negado).
CONCEPT_NEGATIVE_CUES: dict[str, list[str]] = {
    "epe": [
        r"capsular\s+integrity\s+(remains?|is|was|holds?|stays?)\s*(\w+ly\s+)?(intact|preserved|maintained)?",
        r"(organ|gland)[-\s]confined",
        r"capsule\s+(is|remains?|appears?)\s+(\w+ly\s+)?(intact|preserved|continuous|smooth)",
    ],
    "svi": [r"seminal\s+vesicles?\s+(are|is|remain\w*|appear\w*|maintain\w*)\s+(\w+ly\s+)?(normal|symmetric|unremarkable|spared|uninvolved)"],
    "lymphadenopathy": [
        r"lymph\s+nodes?\s+(are|is|remain\w*|appear\w*|maintain\w*|measure)\s+(\w+ly\s+)?(normal|unremarkable|sub[-\s]?centimet|non[-\s]?enlarged)",
        r"(no|without)\s+(suspicious\s+|pathologic\w*\s+|enlarged\s+)*(pelvic\s+)?(lymph\s*(node|adenopathy)|nodal)",
    ],
    "bone_lesion": [
        r"(skeleton|osseous\s+structures?|bones?|bone\s+marrow)\s+(is|are|remain\w*|appear\w*|lacks?|shows?)\s+(\w+ly\s+)?(normal|unremarkable|intact|no\b)",
        r"no\s+(suspicious\s+)?(osseous|bone|skeletal)",
    ],
}

#: Terminadores: cortan el ámbito de la negación (Chapman 2001, §2.2).
TERMINATORS = [
    r"\bbut\b", r"\bhowever\b", r"\balthough\b", r"\bthough\b", r"\byet\b", r"\bexcept\b",
    r"\bapart\s+from\b", r"\baside\s+from\b", r"\bother\s+than\b", r"\bwith\s+the\s+exception\s+of\b",
    r"\bwhereas\b", r"\bwhile\b",
]

_PSEUDO_RE = re.compile("|".join(PSEUDO_NEGATIONS), re.I)
_PRE_RE = re.compile("|".join(PRE_NEGATIONS), re.I)
_POST_RE = re.compile("|".join(POST_NEGATIONS), re.I)
_TERM_RE = re.compile("|".join(TERMINATORS), re.I)
_CUE_RE = {k: re.compile("|".join(v), re.I) for k, v in CONCEPT_NEGATIVE_CUES.items()}


def split_sentences(text: str) -> list[str]:
    """Segmenta en oraciones. También corta en ``;`` y en saltos de línea."""
    if not text:
        return []
    flat = re.sub(r"\s+", " ", text.replace("\n", ". "))
    parts = re.split(r"(?<=[.;:])\s+", flat)
    return [p.strip() for p in parts if p.strip()]


def _scope_negated(sentence: str, start: int, end: int) -> bool:
    """¿Está el concepto en ``[start, end)`` bajo el ámbito de una negación?

    Se enmascaran primero las pseudo-negaciones; luego se busca una señal de
    pre-negación entre el terminador anterior más cercano y el concepto, y una
    de post-negación entre el concepto y el terminador posterior más cercano.
    """
    s = _PSEUDO_RE.sub(lambda m: "#" * len(m.group()), sentence)

    left = s[:start]
    right = s[end:]

    # Recortar el ámbito en el terminador más próximo a cada lado.
    lt = [m.end() for m in _TERM_RE.finditer(left)]
    if lt:
        left = left[max(lt):]
    rt = [m.start() for m in _TERM_RE.finditer(right)]
    if rt:
        right = right[: min(rt)]

    if _PRE_RE.search(left):
        return True
    if _POST_RE.search(right):
        return True
    return False


def concept_status(text: str, pattern: str, concept: str | None = None) -> float:
    """1.0 afirmado, 0.0 negado, NaN no mencionado.

    Si el concepto aparece varias veces con estados distintos, gana la
    afirmación: en un informe radiológico, un hallazgo afirmado en alguna
    oración es un hallazgo presente. Las señales negativas específicas del
    concepto (``CONCEPT_NEGATIVE_CUES``) tienen prioridad sobre NegEx: son
    formulaciones idiomáticas de ausencia que el ámbito genérico no cubre.
    """
    rx = re.compile(pattern, re.I)
    cue = _CUE_RE.get(concept) if concept else None
    seen = False
    affirmed = False
    for sent in split_sentences(text):
        hits = list(rx.finditer(sent))
        if not hits:
            continue
        seen = True
        if cue is not None and cue.search(sent):
            continue
        for m in hits:
            if not _scope_negated(sent, m.start(), m.end()):
                affirmed = True
                break
        if affirmed:
            return 1.0
    return 0.0 if seen else NAN


# --------------------------------------------------------------------------
# Medidas y localización.
# --------------------------------------------------------------------------

def lesion_size_mm(text: str) -> tuple[float, float]:
    """Diámetro máximo de la lesión y su volumen elipsoidal aproximado.

    Prioriza las medidas tridimensionales ``a x b x c mm``; si no las hay, toma
    la mayor medida en mm mencionada en el texto. PI-RADS v2.1 usa el diámetro
    máximo, y el umbral de 15 mm separa la categoría 4 de la 5.
    """
    if not text:
        return NAN, NAN
    m3 = re.findall(r"(\d+(?:\.\d+)?)\s*[x×]\s*(\d+(?:\.\d+)?)\s*[x×]\s*(\d+(?:\.\d+)?)\s*mm", text, re.I)
    if m3:
        dims = max((tuple(float(v) for v in t) for t in m3), key=max)
        vol = math.pi / 6.0 * dims[0] * dims[1] * dims[2] / 1000.0  # mL
        return max(dims), vol
    m2 = re.findall(r"(\d+(?:\.\d+)?)\s*[x×]\s*(\d+(?:\.\d+)?)\s*mm", text, re.I)
    if m2:
        dims = max((tuple(float(v) for v in t) for t in m2), key=max)
        return max(dims), NAN
    m1 = re.findall(r"(\d+(?:\.\d+)?)\s*mm", text, re.I)
    if m1:
        return max(float(v) for v in m1), NAN
    return NAN, NAN


ZONE_PATTERNS = {
    "zone_peripheral": r"peripheral\s+zone",
    "zone_transition": r"(transition(al)?\s+zone|central\s+gland)",
    "zone_anterior": r"anterior\s+(fibromuscular|stroma|zone|gland)",
}

LOCATION_PATTERNS = {
    "loc_apex": r"\bapex|apical\b",
    "loc_mid": r"\bmid[-\s]?(gland|zone|prostate)?\b",
    "loc_base": r"\bbase\b|\bbasal\b",
}



# --------------------------------------------------------------------------
# Graduación de la señal, en lugar de un binario.
# --------------------------------------------------------------------------

#: PI-RADS v2.1 puntúa difusión y T2 en una escala ordinal, no en presencia /
#: ausencia. El informe conserva esa gradación en el adjetivo ("restricción
#: marcada" frente a "restricción leve"), así que se recupera como ordinal: es
#: más informativo que el binario y además esquiva las oraciones adversativas
#: del tipo "restricción leve, aunque sin restricción marcada", donde el
#: binario negado y el afirmado son ambos defendibles.
_SEVERITY_TIERS = [
    (3.0, r"(marked|pronounced|profound|intense|strong|severe|striking|florid|avid)"),
    (2.0, r"(moderate|intermediate|appreciable|definite|substantial)"),
    (1.0, r"(mild|slight|subtle|minimal|equivocal|faint|low[-\s]grade)"),
]


def _graded(text: str, concept_pat: str, status: float) -> float:
    """Intensidad ordinal 0-3 de un concepto afirmado.

    ``0`` si el concepto está negado, ``NaN`` si no se menciona. Si está
    afirmado pero sin adjetivo de intensidad, se devuelve ``2.0`` (grado por
    defecto: el hallazgo se reporta como presente sin matizar).
    """
    if status != status:
        return NAN
    if status == 0.0:
        return 0.0
    rx = re.compile(concept_pat, re.I)
    best = 2.0
    for sent in split_sentences(text):
        for m in rx.finditer(sent):
            window = sent[max(0, m.start() - 90) : m.end() + 40]
            for score, pat in _SEVERITY_TIERS:
                if re.search(pat, window, re.I):
                    return score
    return best


def extract(clinical: dict) -> dict[str, float]:
    """Bloque D para un caso, a partir de ``clinical['radiology_report']``."""
    text = (clinical or {}).get("radiology_report") or ""
    out: dict[str, float] = {}

    for name, pat in CONCEPTS.items():
        out["rad_" + name] = concept_status(text, pat, name)

    out["rad_dwi_severity"] = _graded(text, CONCEPTS["dwi_restriction"], out["rad_dwi_restriction"])
    out["rad_t2_severity"] = _graded(text, r"(t2[-\s]weighted|t2\s+signal|hypointens\w*)", out["rad_t2_marked_hypo"] if out["rad_t2_marked_hypo"] == out["rad_t2_marked_hypo"] else 1.0)

    size, vol = lesion_size_mm(text)
    out["rad_lesion_max_mm"] = size
    out["rad_lesion_vol_ml"] = vol
    # Umbral PI-RADS v2.1: >=15 mm eleva una lesión de categoría 4 a 5.
    out["rad_lesion_ge15mm"] = float(size >= 15.0) if size == size else NAN
    out["rad_has_measurement"] = float(size == size)

    low = text.lower()
    for name, pat in ZONE_PATTERNS.items():
        out["rad_" + name] = float(bool(re.search(pat, low)))
    for name, pat in LOCATION_PATTERNS.items():
        out["rad_" + name] = float(bool(re.search(pat, low)))
    out["rad_bilateral"] = float(bool(re.search(r"bilateral|both\s+(lobes|sides)", low)))
    out["rad_multifocal"] = float(bool(re.search(r"multifocal|second(ary)?\s+(lesion|focus)|additional\s+(lesion|focus)", low)))

    # Estadio local radiológico agregado: la evidencia de enfermedad avanzada
    # que un informe puede aportar por encima de la categoría PI-RADS.
    adverse = [out["rad_epe"], out["rad_svi"], out["rad_lymphadenopathy"], out["rad_bone_lesion"]]
    present = [a for a in adverse if a == a]
    out["rad_adverse_count"] = float(sum(present)) if present else NAN
    out["rad_adverse_reported"] = float(len(present))

    out["rad_report_len_chars"] = float(len(text))
    return out

"""Extracción verificable: negación, tiempo y fuente (PLAN §4.1, experimento E01).

Corrige tres mecanismos concretos del parser de V1, no «mejora la extracción» en
abstracto. Los tres están demostrados con pruebas sintéticas en EVIDENCIA §3.2:

1. **Alcance de negación.** `No histological progression.` activaba a la vez
   `path_traj_stable` y `path_traj_progress`, porque `progress\\w*` casa dentro
   de la propia negación. Aquí una coincidencia precedida de una señal negativa
   **en la misma oración** produce `value=False, status="observed"`, no un
   positivo.
2. **Cronología.** El delta de ISUP se calculaba como «último menos primero **en
   orden de texto**». Un informe que presenta `Timepoint 2` antes que
   `Timepoint 1` daba el signo cambiado. Aquí los momentos se ordenan por
   **fecha**, y si no hay fecha, por número de timepoint; si no hay ninguna de
   las dos cosas, el delta queda `unknown` en vez de inventarse.
3. **Fuente.** El grado humano y el `AI-predicted` viajan en hechos distintos con
   `source` distinto. Una discrepancia entre ambos es un hecho más, no ruido.

Ausencia de mención **nunca** se convierte en negativa: eso es `unknown`.
"""
from __future__ import annotations

import re
from datetime import datetime

from .evidence import Hecho, RegistroDeHechos

VERSION = "extractor_v2.1"

_MESES = {m.lower(): i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}

# Señales de negación. El alcance es la oración: una negación no cruza un punto.
_NEGACIONES = re.compile(
    r"\b(no|not|non|without|absent|negative\s+for|free\s+of|denies|denied|"
    r"ruled\s+out|lack(?:s|ing)?\s+of|neither|nor|unremarkable\s+for)\b", re.I)

_FIN_ORACION = re.compile(r"[.;:\n]")

_TIMEPOINT = re.compile(r"Timepoint\s+(\d+)\s*(?:\(([^)]*)\))?\s*:", re.I)
_ISUP = re.compile(r"(?:ISUP\s+)?grade\s+group\s+(\d)", re.I)
_GLEASON = re.compile(r"Gleason\s+(\d)\s*\+\s*(\d)", re.I)
_AI_LINEA = re.compile(r"AI-predicted[^\n]*", re.I)

_CONCEPTOS_PATOLOGIA = {
    "cribriform": r"cribriform",
    "intraductal": r"intraductal",
    "perineural_invasion": r"perineural\s+invasion|\bPNI\b",
    "extraprostatic_extension": r"extraprostatic\s+extension|\bEPE\b",
    "seminal_vesicle_invasion": r"seminal\s+vesicle\s+invasion|\bSVI\b",
    "lymphovascular_invasion": r"lymphovascular\s+invasion|\bLVI\b",
    "positive_margins": r"positive\s+(surgical\s+)?margins?",
    "lymph_node_metastasis": r"lymph\s+node\s+metastas[ei]s|\bpN1\b",
}


def negado(texto: str, inicio: int, ventana: int = 60) -> tuple[bool, str | None]:
    """¿La coincidencia en `inicio` cae bajo una negación de su misma oración?

    Devuelve (negado, cita de la señal). El alcance se corta en el signo de
    puntuación anterior: sin ese corte, «Stable disease. Progression noted.»
    heredaría una negación de la frase de antes.
    """
    arranque = max(0, inicio - ventana)
    previo = texto[arranque:inicio]
    corte = None
    for m in _FIN_ORACION.finditer(previo):
        corte = m.end()
    if corte is not None:
        previo = previo[corte:]
    señales = list(_NEGACIONES.finditer(previo))
    if not señales:
        return False, None
    return True, señales[-1].group(0)


def _fecha(etiqueta: str | None):
    if not etiqueta:
        return None
    m = re.search(r"([A-Za-z]{3})[a-z]*\.?\s+(\d{4})", etiqueta)
    if m and m.group(1).lower() in _MESES:
        return datetime(int(m.group(2)), _MESES[m.group(1).lower()], 1)
    m = re.search(r"\b(\d{4})\b", etiqueta)
    return datetime(int(m.group(1)), 1, 1) if m else None


def segmentar(texto: str) -> list[dict]:
    """Momentos del informe, **ordenados por fecha**, no por posición en el texto."""
    marcas = list(_TIMEPOINT.finditer(texto))
    if not marcas:
        return [{"nombre": "sin_momento", "numero": None, "fecha": None,
                 "etiqueta_fecha": None, "inicio": 0, "fin": len(texto),
                 "orden_texto": 0, "orden_cronologico": 0,
                 "orden_por": "sin_momentos_marcados", "desordenado_en_texto": False}]
    segmentos = []
    for i, m in enumerate(marcas):
        fin = marcas[i + 1].start() if i + 1 < len(marcas) else len(texto)
        segmentos.append({
            "nombre": f"timepoint_{m.group(1)}",
            "numero": int(m.group(1)),
            "fecha": _fecha(m.group(2)),
            "etiqueta_fecha": (m.group(2) or "").strip() or None,
            "inicio": m.start(), "fin": fin, "orden_texto": i,
        })
    con_fecha = all(s["fecha"] for s in segmentos)
    clave = (lambda s: s["fecha"]) if con_fecha else (lambda s: s["numero"])
    ordenados = sorted(segmentos, key=clave)
    for k, s in enumerate(ordenados):
        s["orden_cronologico"] = k
        s["orden_por"] = "fecha" if con_fecha else "numero_de_timepoint"
        s["desordenado_en_texto"] = s["orden_cronologico"] != s["orden_texto"]
    return ordenados


def extraer_patologia(clinical: dict, case_id: str = "") -> RegistroDeHechos:
    reg = RegistroDeHechos(case_id)
    texto = (clinical or {}).get("pathology_report") or ""
    fuente = "pathology_report"
    if not texto.strip():
        for c in list(_CONCEPTOS_PATOLOGIA) + ["isup_humano", "isup_delta", "progresion_histologica"]:
            reg.añadir(Hecho(c, None, "unknown", fuente, VERSION,
                             nota="informe ausente; ausencia no es negativa"))
        return reg

    cuerpo_humano = _AI_LINEA.split(texto)[0]
    segmentos = segmentar(cuerpo_humano)

    # --- Grado humano por momento, en orden cronológico ---
    isups = []
    for s in segmentos:
        trozo = cuerpo_humano[s["inicio"]:s["fin"]]
        for m in _ISUP.finditer(trozo):
            ini, fin = s["inicio"] + m.start(), s["inicio"] + m.end()
            reg.añadir(Hecho("isup_humano", float(m.group(1)), "observed", fuente, VERSION,
                             (ini, fin), cuerpo_humano[ini:fin], s["nombre"]))
            isups.append((s["orden_cronologico"], float(m.group(1))))
        for m in _GLEASON.finditer(trozo):
            ini, fin = s["inicio"] + m.start(), s["inicio"] + m.end()
            reg.añadir(Hecho("gleason_humano", (int(m.group(1)), int(m.group(2))), "observed",
                             fuente, VERSION, (ini, fin), cuerpo_humano[ini:fin], s["nombre"]))

    if len(isups) >= 2:
        isups.sort(key=lambda x: x[0])
        delta = isups[-1][1] - isups[0][1]
        reg.añadir(Hecho("isup_delta", delta, "observed", fuente, VERSION,
                         timepoint="cronologico",
                         nota=f"orden por {segmentos[0].get('orden_por')}; "
                              f"{sum(s.get('desordenado_en_texto', False) for s in segmentos)} "
                              "momentos aparecen desordenados en el texto"))
    elif len(isups) == 1:
        reg.añadir(Hecho("isup_delta", 0.0, "observed", fuente, VERSION,
                         nota="un solo momento documentado"))
    else:
        reg.añadir(Hecho("isup_delta", None, "unknown", fuente, VERSION,
                         nota="sin grado humano legible"))

    # --- Progresión histológica, con negación ---
    patron = re.compile(r"(progress\w*|upgrad\w*|increase\s+in\s+grade|higher\s+grade\s+than)", re.I)
    hallazgos = list(patron.finditer(cuerpo_humano))
    if hallazgos:
        for m in hallazgos:
            neg, señal = negado(cuerpo_humano, m.start())
            reg.añadir(Hecho("progresion_histologica", not neg, "observed", fuente, VERSION,
                             (m.start(), m.end()), m.group(0),
                             nota=f"negado por «{señal}»" if neg else None))
    else:
        reg.añadir(Hecho("progresion_histologica", None, "unknown", fuente, VERSION,
                         nota="no se menciona; ausencia no es negativa"))

    # --- Conceptos binarios, con negación ---
    for nombre, pat in _CONCEPTOS_PATOLOGIA.items():
        ms = list(re.finditer(pat, cuerpo_humano, re.I))
        if not ms:
            reg.añadir(Hecho(nombre, None, "unknown", fuente, VERSION,
                             nota="no se menciona; ausencia no es negativa"))
            continue
        for m in ms:
            neg, señal = negado(cuerpo_humano, m.start())
            reg.añadir(Hecho(nombre, not neg, "observed", fuente, VERSION,
                             (m.start(), m.end()), m.group(0),
                             nota=f"negado por «{señal}»" if neg else None))

    # --- Predicción de patología digital: fuente distinta, hecho distinto ---
    ai = _AI_LINEA.search(texto)
    if ai:
        g = _ISUP.search(ai.group(0))
        if g:
            ini = ai.start() + g.start()
            reg.añadir(Hecho("isup_ai", float(g.group(1)), "observed", fuente, VERSION,
                             (ini, ini + len(g.group(0))), g.group(0),
                             nota="predicción de patología digital, NO lectura humana"))
    humano = reg.valor("isup_humano", timepoint=segmentos[-1]["nombre"]) if segmentos else None
    prediccion = reg.valor("isup_ai")
    if humano is not None and prediccion is not None:
        reg.añadir(Hecho("discrepancia_grado_humano_ai", humano != prediccion, "observed",
                         fuente, VERSION,
                         nota=f"humano {humano} vs digital {prediccion}"))
    return reg

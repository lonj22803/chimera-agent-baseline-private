"""E01 — ¿negación, tiempo y fuente mejoran la extracción? (PLAN §11)

Comparador: el parser de V1 (`features_pathology.extract`).
Medición: contradicciones, afirmaciones con fuente válida, cobertura y —lo que
más importa— **cuántos hechos cambian de valor**, separando los que pasan de
«afirmado» a «desconocido» de los que cambian de signo.

Lo que este experimento **no** puede cerrar: la exactitud de los conceptos
contra una revisión humana ciega, que el PLAN §10.2 exige y ninguna máquina
puede sustituir. Aquí se mide mecanismo, no verdad clínica.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
AQUI = Path(__file__).resolve().parent

CLINICO = {1: "prostate-biopsy-decision-clinical-data.json",
           2: "prostate-treatment-decision-clinical-data.json",
           3: "prostate-time-to-recurrence-or-last-follow-up-clinical-data.json"}


def main() -> None:
    import sys
    sys.path.insert(0, str(RAIZ))
    from version_final_reto.common.chimera_experts.features_pathology import extract as v1
    from version_final_reto.investigacion.common.extractors import extraer_patologia, segmentar

    r = {"alcance": "E01: mecanismo de extracción, no exactitud clínica revisada",
         "por_tarea": {}, "global": {}}
    tot = Counter()
    ejemplos = {"contradiccion_v1": [], "desorden_cronologico": [], "cambio_de_signo": []}

    for tarea in (1, 2, 3):
        base = RAIZ / f"data/task{tarea}/agent_input"
        c = Counter()
        for d in sorted(p for p in base.iterdir() if p.is_dir()):
            f = d / CLINICO[tarea]
            if not f.exists():
                continue
            clinical = json.loads(f.read_text())
            texto = clinical.get("pathology_report") or ""
            c["casos"] += 1
            if not texto.strip():
                c["sin_informe"] += 1

            viejo = v1(clinical)
            nuevo = extraer_patologia(clinical, d.name)

            # 1. Contradicción de V1: estable y progresión a la vez.
            if viejo.get("path_traj_stable") == 1 and viejo.get("path_traj_progress") == 1:
                c["contradiccion_v1"] += 1
                if len(ejemplos["contradiccion_v1"]) < 3:
                    ejemplos["contradiccion_v1"].append(
                        {"tarea": tarea, "caso": d.name,
                         "v2_progresion": nuevo.valor("progresion_histologica"),
                         "cita": texto[:110]})

            # 2. Desorden cronológico que V1 no veía.
            segs = segmentar(texto) if texto.strip() else []
            if any(s.get("desordenado_en_texto") for s in segs):
                c["desorden_cronologico"] += 1
                if len(ejemplos["desorden_cronologico"]) < 3:
                    ejemplos["desorden_cronologico"].append({"tarea": tarea, "caso": d.name})

            # 3. Delta de ISUP: signo de V1 (orden de texto) vs V2 (cronológico).
            d_v1, d_v2 = viejo.get("path_isup_delta"), nuevo.valor("isup_delta")
            if d_v1 is not None and d_v2 is not None and d_v1 == d_v1:  # no NaN
                if d_v1 != d_v2:
                    c["delta_distinto"] += 1
                    if (d_v1 > 0) != (d_v2 > 0) and len(ejemplos["cambio_de_signo"]) < 3:
                        ejemplos["cambio_de_signo"].append(
                            {"tarea": tarea, "caso": d.name, "v1": d_v1, "v2": d_v2})

            # 4. Integridad de citas: toda cita tiene que cuadrar con su fuente.
            malos = nuevo.sin_respaldo({"pathology_report": texto})
            c["hechos"] += len(nuevo)
            c["hechos_sin_respaldo"] += len(malos)
            c["conflictos_declarados"] += len(nuevo.conflictos())
            for h in nuevo:
                c[f"estado_{h.status}"] += 1
                # Lo que V1 no podía representar: negativa documentada frente a
                # ausencia de mención. V1 colapsaba ambas en 0.
                if h.status == "observed" and h.value is False:
                    c["negativas_documentadas"] += 1
                if h.status == "unknown":
                    c["ausencias_no_convertidas_en_negativa"] += 1

        r["por_tarea"][f"task{tarea}"] = dict(sorted(c.items()))
        tot.update(c)

    hechos = tot["hechos"] or 1
    r["global"] = dict(sorted(tot.items()))
    r["global"]["pct_hechos_con_fuente_valida"] = round(
        100 * (hechos - tot["hechos_sin_respaldo"]) / hechos, 4)
    r["ejemplos"] = ejemplos
    destino = AQUI / "reports" / "e01_extraccion.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(r, indent=2, ensure_ascii=False))

    g = r["global"]
    print(f"casos con informe de patología : {g['casos'] - g.get('sin_informe', 0)} de {g['casos']}")
    print(f"hechos extraídos               : {g['hechos']}")
    print(f"  con fuente válida            : {g['pct_hechos_con_fuente_valida']}%  "
          f"({g['hechos_sin_respaldo']} sin respaldo)")
    print(f"  observados                   : {g.get('estado_observed', 0)}")
    print(f"  desconocidos (no negativos)  : {g.get('estado_unknown', 0)}")
    print(f"  negativas DOCUMENTADAS       : {g.get('negativas_documentadas', 0)}  "
          "<- V1 no las distinguía de una ausencia")
    print()
    print(f"contradicciones de V1 (estable Y progresión) : {g.get('contradiccion_v1', 0)}")
    print(f"informes con momentos desordenados en texto  : {g.get('desorden_cronologico', 0)}")
    print(f"deltas de ISUP que cambian al ordenar por fecha: {g.get('delta_distinto', 0)}")
    print(f"conflictos declarados por V2                 : {g.get('conflictos_declarados', 0)}")
    print(f"\nescrito {destino.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()

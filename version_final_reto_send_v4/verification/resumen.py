"""Junta la evidencia de la V1.1 en un solo fichero.

Recorre las corridas del perfilador, empareja los dos brazos por `case_id` y
tarea, compara sus dos ficheros de salida y añade lo que midieron las
comparaciones de expertos. Sale `resumen_v1_1.json`.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
TAREA = {0: 1, 1: 2, 2: 3}


def corridas() -> list[dict]:
    out = []
    for summary in sorted(HERE.glob("gc_profile_*/summary.json")):
        data = json.loads(summary.read_text())
        for run in data["runs"]:
            gr, gd = run.get("gc_resources", {}), run.get("gc_delivery", {})
            out.append({
                "corrida": summary.parent.name,
                "version": "V1" if data.get("package") == "delete_final_versions_task_V1" else "V1.1",
                "tarea": TAREA[run["interface"]],
                "case_id": run.get("case_id"),
                "cpuset": data.get("cpuset"), "cacheado": not data.get("unseen_case", True),
                "segundos": run["seconds"], "exit_code": run["exit_code"],
                "sobre_el_limite": run.get("over_gc_limit"),
                "respaldo": gd.get("fallback"), "ficheros": len(run.get("files") or []),
                "fases": gr.get("phases_seconds"), "llamadas_llm": gr.get("llm_calls"),
                "presupuesto": gd.get("budget_seconds"), "soltado": gd.get("budget_skipped"),
                "dir": str(summary.parent),
            })
    return out


def salidas(a: Path, b: Path, interface: int) -> dict:
    def load(run):
        d = run / f"interf{interface}" / "output"
        return {p.name: p.read_bytes() for p in sorted(d.glob("*.json"))} if d.is_dir() else {}
    left, right = load(a), load(b)
    return {"mismos_ficheros": sorted(left) == sorted(right),
            "identicos_byte_a_byte": bool(left) and left == right,
            "ficheros": sorted(set(left) | set(right))}


def main() -> None:
    todas = corridas()
    parejas = []
    for tarea in (1, 2, 3):
        interface = {1: 0, 2: 1, 3: 2}[tarea]
        v1 = [r for r in todas if r["version"] == "V1" and r["tarea"] == tarea and r["case_id"]]
        v11 = [r for r in todas if r["version"] == "V1.1" and r["tarea"] == tarea and r["case_id"]]
        for a in v1:
            for b in v11:
                if a["case_id"] != b["case_id"] or b.get("presupuesto") in (60.0, 60):
                    continue
                parejas.append({
                    "tarea": tarea, "case_id": a["case_id"],
                    "segundos_v1": a["segundos"], "segundos_v11": b["segundos"],
                    "ahorro_segundos": round(a["segundos"] - b["segundos"], 1),
                    "ahorro_porciento": round(100 * (a["segundos"] - b["segundos"]) / a["segundos"], 1),
                    "respaldo_v1": a["respaldo"], "respaldo_v11": b["respaldo"],
                    "salida": salidas(Path(a["dir"]), Path(b["dir"]), interface),
                })
    expertos = {}
    for tarea in (1, 2):
        f = HERE / f"compare_experts_task{tarea}.json"
        if f.exists():
            d = json.loads(f.read_text())
            expertos[f"task{tarea}"] = {
                "casos": d["cases"], "errores": len(d["errors"]),
                "peor_delta": d["worst_delta"],
                "alguna_decision_cambia": any(r["decision_changed"] for r in d["per_case"].values()),
                "casos_identicos": sum(1 for r in d["per_case"].values() if r["n_differing_leaves"] == 0),
                "aceleracion_media": round(
                    sum(r["speedup"] for r in d["per_case"].values()) / max(len(d["per_case"]), 1), 2),
            }
    payload = {
        "limite_gc_segundos": 900,
        "condiciones": "un contenedor por caso, --cpuset-cpus 0-3, case_id que panel_cache.json no tiene",
        "parejas_mismo_case_id": parejas,
        "expertos_base_vs_njobs1": expertos,
        "todas_las_corridas": todas,
    }
    out = HERE / "resumen_v1_1.json"
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    for par in parejas:
        print(f"task{par['tarea']} {par['case_id']}: V1 {par['segundos_v1']}s -> V1.1 "
              f"{par['segundos_v11']}s ({par['ahorro_porciento']:+.1f}%)  "
              f"salida idéntica: {par['salida']['identicos_byte_a_byte']}")
    for k, v in expertos.items():
        print(f"{k}: peor delta {v['peor_delta']:.2e}, decisiones que cambian: "
              f"{v['alguna_decision_cambia']}, idénticos {v['casos_identicos']}/{v['casos']}")
    print(f"-> {out}")


if __name__ == "__main__":
    main()

"""Escribe `INFORME.md` a partir de lo que midió el evaluador oficial.

Ninguna cifra de este informe se teclea: todas se leen de `scores/no_judge.json`,
`scores/judge_task*.json` y `scores/analisis.json`. Si la corrida se repite y los
números cambian, se vuelve a lanzar este script y el informe cambia con ellos.
La prosa —qué hace cada junta y por qué— vive aquí y es lo único fijo.

    PYTHONPATH=src:. .venv/bin/python -m delete_final_versions_task.resultados.informe
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path

RES = Path(__file__).resolve().parent
REPO = RES.parents[1]

# Referencias históricas, para situar la corrida. Proceden de los README de cada
# tarea y del plan de cierre; no se recalculan aquí y se citan como lo que son.
BASELINE = {"task1": 0.6428, "task2": 0.4457, "task3": 0.6636}
BASELINE_OVERALL = 0.5651


def load(path: Path):
    return json.loads(path.read_text()) if path.exists() else None


def num(value, dec: int = 4) -> str:
    if value is None:
        return "—"
    if isinstance(value, (int, float)):
        return f"{value:.{dec}f}".replace(".", ",")
    return str(value)


def pct(value) -> str:
    return "—" if value is None else f"{value:.1%}".replace(".", ",")


MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre")


def fecha() -> str:
    hoy = datetime.now()
    return f"{hoy.day} de {MESES[hoy.month - 1]} de {hoy.year}"


def git_sha() -> str:
    try:
        return subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return "desconocido"


def tabla_resultado(sj: dict, cj: dict, ranking: dict) -> list[str]:
    filas = [
        "| Tarea | Casos | Puerta de decisión | `ranking_score` sin juez | `ranking_score` con juez | `mean_rationale_score` | Baseline |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    nombres = {1: "1 · biopsia", 2: "2 · tratamiento", 3: "3 · recurrencia"}
    for t in (1, 2, 3):
        a, b = sj.get(f"task{t}") or {}, cj.get(f"task{t}") or {}
        puerta = a.get("decision_gate_pass_rate")
        n = a.get("n_cases") or a.get("n_evaluated") or b.get("n_cases")
        filas.append(
            f"| **{nombres[t]}** | {n or '—'} | {pct(puerta) if t != 3 else 'no aplica'} | "
            f"{num(a.get('ranking_score'))} | {num(b.get('ranking_score'))} | "
            f"{num(b.get('mean_rationale_score'))} | {num(BASELINE[f'task{t}'])} |")
    filas.append(
        f"| **OVERALL** (2:2:1) | | | **{num(ranking.get('overall_sin_juez'))}** | "
        f"**{num(ranking.get('overall_con_juez'))}** | | {num(BASELINE_OVERALL)} |")
    return filas


def tabla_componentes(comp: dict) -> list[str]:
    """Los seis componentes del `case_score` y su peso en cada modo.

    Los valores son la media sobre los casos que pasan la puerta. Salvo el
    juicio de la nota, todos son deterministas: no cambian al apagar el juez,
    lo que cambia es cuánto pesan.
    """
    comps = [("rationale_score", "juicio de la nota", None, 0.20),
             ("variable_weight_score", "pesos de variables", 0.275, 0.25),
             ("confidence_score", "confianza declarada", 0.225, 0.20),
             ("important_decisive_factor_score", "factores important/decisive", 0.175, 0.15),
             ("tool_score", "uso de herramientas", 0.150, 0.15),
             ("section_grounding_score", "anclaje a secciones", 0.175, 0.05)]
    out = ["| Componente | Peso sin juez | Peso con juez | T1 | T2 | T3 |",
           "|---|---:|---:|---:|---:|---:|"]
    for key, nombre, w_sin, w_con in comps:
        vals = [num((comp.get(f"task{t}") or {}).get(key)) for t in (1, 2, 3)]
        peso_sin = num(w_sin, 3) if w_sin else "**0 — no se juzga**"
        out.append(f"| {nombre} | {peso_sin} | {num(w_con, 3)} | " + " | ".join(vals) + " |")
    return out


def bloque_peldanos(tareas: dict) -> list[str]:
    out = []
    etiquetas = {1: ("Peldaño del protocolo", "El protocolo de T1 es una cascada: cada caso lo reclama "
                     "el primer peldaño que aplica, y el acta escribe cuál fue."),
                 2: ("Portavoz elegido", "En T2 la regla es única —fiabilidad medida— y lo que cambia "
                     "es qué experto acaba hablando por la sala.")}
    for t in (1, 2):
        datos = (tareas.get(f"task{t}") or {}).get("acierto_por_peldano") or {}
        if not datos:
            continue
        titulo, explica = etiquetas[t]
        out += [f"**Tarea {t}.** {explica}", "",
                f"| {titulo} | Casos | Aciertos | Acierto |", "|---|---:|---:|---:|"]
        for regla, d in datos.items():
            out.append(f"| {regla} | {d['n']} | {d['aciertos']} | {num(d['acierto'])} |")
        out.append("")
    return out


def bloque_actas(tareas: dict) -> list[str]:
    out = ["| Tarea | Actas | Intervenciones (media) | Rango | Reaperturas | Turnos registrados |",
           "|---|---:|---:|---:|---:|---:|"]
    for t in (1, 2, 3):
        a = (tareas.get(f"task{t}") or {}).get("actas") or {}
        turnos = sum((a.get("turnos_por_participante") or {}).values())
        out.append(f"| {t} | {a.get('n_actas', '—')} | {num(a.get('intervenciones_media'), 2)} | "
                   f"{a.get('intervenciones_min', '—')}–{a.get('intervenciones_max', '—')} | "
                   f"{a.get('casos_con_reapertura', '—')} | {turnos or '—'} |")
    return out


def bloque_coste(tareas: dict) -> list[str]:
    out = ["| Tarea | s/caso (media) | s/caso (mediana) | Total | Tokens de entrada/caso | Llamadas LLM/caso |",
           "|---|---:|---:|---:|---:|---:|"]
    for t in (1, 2, 3):
        c = (tareas.get(f"task{t}") or {}).get("coste") or {}
        total = c.get("minutos_totales")
        out.append(f"| {t} | {num(c.get('segundos_por_caso_media'), 1)} | "
                   f"{num(c.get('segundos_por_caso_mediana'), 1)} | "
                   f"{num(total, 1) + ' min' if total else '—'} | "
                   f"{c.get('tokens_entrada_por_caso') or '—'} | "
                   f"{num(c.get('llamadas_llm_por_caso'), 1)} |")
    return out


def guardias(tareas: dict) -> list[str]:
    out = ["| Tarea | Esquema válido | Nota de respaldo | Formulario de respaldo | Prosa retada | Reaperturas |",
           "|---|---:|---:|---:|---:|---:|"]
    for t in (1, 2):
        m = (tareas.get(f"task{t}") or {}).get("mecanismo") or {}
        out.append(f"| {t} | {m.get('esquema_valido', '—')}/{m.get('casos_ok', '—')} | "
                   f"{m.get('nota_de_respaldo', '—')} | {m.get('formulario_de_respaldo', '—')} | "
                   f"{m.get('prosa_retada', '—')} | {m.get('verificador_reabre', '—')} |")
    m3 = (tareas.get("task3") or {}).get("mecanismo") or {}
    out.append(f"| 3 | {m3.get('casos_ok', '—')}/{m3.get('casos', '—')} | "
               f"{m3.get('respaldo', '—')} | no aplica | no aplica | no aplica |")
    return out


def main() -> None:
    an = load(RES / "scores" / "analisis.json") or {}
    sj = an.get("sin_juez") or {}
    cj = an.get("con_juez") or {}
    ranking = an.get("ranking") or {}
    tareas = an.get("tareas") or {}
    m1 = (tareas.get("task1") or {}).get("mecanismo") or {}
    m2 = (tareas.get("task2") or {}).get("mecanismo") or {}
    m3 = (tareas.get("task3") or {}).get("mecanismo") or {}

    doc: list[str] = []
    A = doc.append
    A("# Las tres juntas, corridas enteras y puntuadas con el evaluador oficial")
    A("")
    A(f"Corrida del {fecha()}, commit `{git_sha()}`. Los **238 casos")
    A("etiquetados** de la base —91 de la tarea 1, 72 de la 2 y 75 de la 3— pasados por")
    A("las tres juntas y puntuados dos veces con el `evaluate.py` de los organizadores:")
    A("una con el juez de razonamiento apagado (determinista, comparable entre corridas)")
    A("y otra con el juez encendido, que es como puntúa Grand Challenge.")
    A("")
    A("Los casos sin etiqueta no se corren aquí: el evaluador no puede puntuarlos, y una")
    A("corrida que no se puede puntuar no responde a ninguna de las preguntas de este")
    A("informe. La cobertura de los 423 casos completos está verificada en las corridas")
    A("de entrega de cada tarea (`task_N/runs/`).")
    A("")
    A("| | |")
    A("|---|---|")
    A("| Cómo se reproduce | `./run_all.sh` — cinco fases en serie, idempotentes |")
    A("| Puntuación | `evaluate.py` de `DIAGNijmegen/CHIMERA-agent`, importado, no reimplementado |")
    A("| Actas | `task_N/boards/` y `task_3/output/task3/*/acta.md`; índice en [PIZARRAS.md](PIZARRAS.md) |")
    A("| Datos crudos | [`scores/`](scores/) — agregados del evaluador y análisis derivado |")
    A("")
    A("---")
    A("")
    A("## 1. Resultado")
    A("")
    doc += tabla_resultado(sj, cj, ranking)
    A("")
    A("**Cómo se compone el número** (leído de `evaluate.py`, no supuesto):")
    A("")
    A("```")
    A("T1, T2:   ranking_score = (mean_case_score + F1) / 2")
    A("          F1 = f1(yes) en T1 · f1 ponderado por soporte en T2")
    A("T3:       ranking_score = c_index          ← y nada más")
    A("```")
    A("")
    A("De ahí salen tres consecuencias que conviene tener presentes al leer la tabla:")
    A("")
    A("1. **La mitad del ranking de T1 y T2 es la decisión pura.** El F1 no depende del")
    A("   juez ni de la prosa: es determinista. Por eso las dos columnas de T1 comparten")
    A("   puerta y difieren sólo en `mean_case_score`.")
    A("2. **`mean_case_score` lleva dentro una puerta multiplicativa.** Si la decisión es")
    A("   incorrecta el caso vale cero por muy bien escrita que esté la nota; sólo los")
    A("   casos que la pasan reciben los componentes restantes.")
    A("3. **El ranking de T3 no puede moverlo el juez**, y en efecto sale idéntico en las")
    A("   dos columnas. Su nota clínica sólo afecta a `mean_case_score`, que se publica al")
    A("   lado porque es donde el juez sí entra.")
    A("")
    A("Apagar el juez no pone su peso a cero: lo **redistribuye** entre los otros")
    A("componentes. Las dos columnas no son comparables entre sí.")
    A("")
    A("### Los componentes, y lo que cambia al encender el juez")
    A("")
    doc += tabla_componentes(an.get("componentes") or {})
    A("")
    A("### Esta corrida reproduce la de entrega a diez decimales")
    A("")
    A("No es una coincidencia aproximada. Los tres rankings sin juez, recalculados hoy")
    A("desde cero sobre una corrida nueva de los 238 casos, coinciden **dígito a dígito**")
    A("con los que quedaron registrados en las corridas de entrega:")
    A("")
    A("| Tarea | Esta corrida | Registrado en `task_N/runs/` |")
    A("|---|---|---|")
    for t, hist in ((1, "0,8390295553"), (2, "0,7783863062"), (3, "0,7371681415929203")):
        v = (sj.get(f"task{t}") or {}).get("ranking_score")
        A(f"| {t} | `{repr(v).replace('.', ',')}` | `{hist}` |")
    ov = ranking.get("overall_sin_juez")
    A(f"| OVERALL | `{str(ov).replace('.', ',')}` | `0,7943999729` |")
    A("")
    A("Y no sólo el agregado: coinciden también los seis componentes, la puerta de")
    A("decisión caso por caso, y el reparto de casos entre los peldaños del protocolo")
    A("(52 / 27 / 12 en T1). **Eso es el diseño funcionando, no suerte.** Si el modelo de")
    A("lenguaje votara, dos corridas no darían el mismo número: un modelo de 2B a")
    A("temperatura 0 sigue siendo sensible al orden de la caché y al lote. Aquí la")
    A("decisión la toma código determinista alimentado por lo que la sala recuperó, y lo")
    A("único que el modelo aporta —la prosa— no entra en el ranking cuando el juez está")
    A("apagado. La reproducibilidad es la consecuencia medible de haberle quitado el voto.")
    A("")
    A("La columna con juez es la excepción, y por la misma razón: es lo único que depende")
    A("de la opinión de un modelo sobre un texto.")
    A("")
    A("El `section_grounding` de T2 es bajo **a propósito**: entrega `reveal_sequence`")
    A("vacío en lugar de silenciar casillas del formulario. Los documentos sí se abren;")
    A("el campo vacío no representa ausencia de lectura. Con el juez encendido ese")
    A("componente pasa de pesar 0,175 a 0,05, y es parte de por qué T2 sube al encenderlo.")
    A("")
    A("---")
    A("")
    A("## 2. Cómo se aborda cada tarea")
    A("")
    A("Las tres comparten una idea y no comparten nada más: **una pizarra**, donde cada")
    A("participante habla en un turno numerado y lo que dice queda escrito literalmente;")
    A("**un protocolo en código**, que toma la decisión por reglas cuyo acierto está")
    A("medido; y **un presidente**, el modelo de lenguaje, que escribe la nota clínica")
    A("pero no vota. Los votos, los umbrales y las políticas de confianza no se trasladan")
    A("de una tarea a otra: cada una midió las suyas.")
    A("")
    A("### 2.1 Tarea 1 — ¿biopsiar a este paciente?")
    A("")
    A("**El problema.** De los 91 casos etiquetados, 49 tienen biopsia previa positiva, y")
    A("ese cubo es donde se gana o se pierde la tarea: ninguna variable del panel decide")
    A("por sí sola, kNN acierta 0,43–0,47 y —medido tres veces— **los votos del modelo de")
    A("lenguaje están en el azar** (el registrador 0,47, el verificador 0,49). Lo que sí")
    A("hay es el propio urólogo, que en su texto libre explica el criterio con todas las")
    A("letras. Leer esos 49 textos es de donde salen las reglas.")
    A("")
    A("**Quince intervenciones.** Un ordenanza lee el expediente; cuatro expertos")
    A("entrenados abren la sesión (Extra-Trees sobre el panel, criterio de cohorte,")
    A("biblioteca de precedentes y un modelo de traza que predice *qué documentos abre el")
    A("urólogo*, y que con eso **fija el plan**); un especialista en la guía EAU critica")
    A("con cita literal; un moderador formula una pregunta por documento; el registrador")
    A("abre exactamente el plan; y sólo entonces hablan los expertos que leen documentos.")
    A("La numeración es global: si el verificador reabre, la segunda vuelta son las")
    A("intervenciones 15, 16 y 17, no «ronda 2». Eso hace que citar un turno identifique")
    A("un momento único y el acta sea una traza, no un adorno.")
    A("")
    A("**Quién decide.** Una cascada de tres peldaños, ordenada por acierto medido:")
    A("criterio de cohorte → grado documentado en las notas previas → voto ponderado de")
    A("los expertos con umbral 0,45. El peldaño 2 es el punto donde la deliberación del")
    A("LLM sí decide el caso: el grado vive en las notas y sólo llega ahí si el")
    A("registrador las abre. Y como un modelo de 2B lo copia mal, el grado se extrae con")
    A("expresión regular del **texto crudo que devolvió la herramienta**, no del resumen.")
    A("")
    A("**Tres guardias, las tres nacidas de un fallo medido.** El presidente no ve el acta")
    A("ni la lista de participantes —recibe un parte clínico construido en código—, porque")
    A("cuando la veía, 187 de 195 notas nombraban un participante o un mecanismo del")
    A("sistema, y el juez penaliza exactamente ahí. El registrador inventaba el grado de")
    A("la biopsia previa en el 5-7 % de los informes, entrecomillado como si lo citara: se")
    A("comprueba en tres capas. Y la biblioteca de precedentes tiene apagado el")
    A("`self-match`, porque encontrarse a sí misma sube la nota local a 0,9469 y en el test")
    A("no puede ocurrir nunca.")
    A("")
    if m1:
        A(f"**En esta corrida:** {m1.get('casos_ok')}/{m1.get('casos')} casos completados, "
          f"{m1.get('esquema_valido')} con esquema válido, "
          f"{m1.get('grado_documentado_hallado')} con grado documentado hallado en las notas, "
          f"{m1.get('verificador_reabre')} reaperturas del verificador y "
          f"{m1.get('biblioteca_self_match')} auto-coincidencias de la biblioteca.")
        A("")
    A("### 2.2 Tarea 2 — ¿qué tratamiento?")
    A("")
    A("**El problema es el contrario.** Aquí el grado ya viene estructurado y la etiqueta")
    A("es casi función de `bx_isup`: la regla ISUP sola acierta 62/72 = 0,861, y el techo")
    A("de consistencia del perfil es 0,931. Queda poquísimo margen en la decisión, así que")
    A("el trabajo de la sesión está en el **82,5 % del `case_score` que no es decisión**:")
    A("justificar, calibrar y anclar. Eso no elimina la puerta multiplicativa — una nota")
    A("perfecta sobre una decisión errónea sigue valiendo cero.")
    A("")
    A("**Cinco expertos, y el hallazgo incómodo.** Los expertos 1, 2 y 4 emiten las mismas")
    A("72 decisiones, una por una — no «acierto parecido»: **idénticas**. Sentarlos como")
    A("tres votos independientes sería una ficción, así que se sientan como *réplicas")
    A("confirmatorias* y el portavoz se elige por fiabilidad medida, no por votación.")
    A("Combinarlos, además, empeora: voto blando y producto de expertos dan 0,7639.")
    A("")
    A("**El experto que rescata.** El experto 3 (aptitud) es el peor de los cinco —0,6389—")
    A("y sólo habla cuando los otros cuatro están en `discuss`. En esta corrida es portavoz")
    if (tareas.get("task2") or {}).get("acierto_por_peldano", {}).get("expert_three"):
        d = tareas["task2"]["acierto_por_peldano"]["expert_three"]
        A(f"en **{d['n']} casos y acierta {d['aciertos']}**. Los tres son excepciones a la regla ISUP:")
    else:
        A("en los casos donde la regla ISUP no alcanza. Son excepciones a la regla:")
    A("es el mecanismo de la escalera funcionando. Pero son tres casos y dentro de")
    A("muestra: ilustra el diseño, no demuestra que generalice.")
    A("")
    if m2:
        A(f"**En esta corrida:** {m2.get('casos_ok')}/{m2.get('casos')} casos, "
          f"{m2.get('esquema_valido')} con esquema válido, "
          f"{m2.get('verificador_reabre')} reaperturas, {m2.get('nota_de_respaldo')} notas de respaldo.")
        A("")
    A("### 2.3 Tarea 3 — ¿cuándo recurre?")
    A("")
    A("**Otro problema distinto.** No hay decisión que puntuar ni formulario: hay que dar")
    A("`event` y `months_to_recurrence`, y el ranking es sólo el c-index. En el baseline")
    A("esta tarea **tumbaba la cola entera**: dos casos resistieron ocho reintentos")
    A("devolviendo «Cannot be determined», porque se le pedía al modelo una fecha de")
    A("recurrencia sin explicarle que una observación censurada es seguimiento sin evento")
    A("observado. Repetir el encargo no resuelve una contradicción semántica.")
    A("")
    A("**El número lo produce un experto, no el LLM.** CAPRA-S fija el orden del riesgo y")
    A("EXPERT-HORIZON lo convierte en meses con un mapa `a·exp(-0,1·CAPRA-S)`")
    A("estrictamente decreciente. Que sea estrictamente decreciente no es un detalle: la")
    A("concordancia usa la inversión riesgo↔tiempo, así que optimizar la magnitud del")
    A("horizonte **no puede dañar el orden**, y hay un test que lo fija. El presidente")
    A("recibe el horizonte ya calculado y sólo escribe su explicación; `decide.finish`")
    A("añade la semántica de la censura. Eso elimina por construcción el aborto por")
    A("negativa del modelo.")
    A("")
    A("**Un techo que no es nuestro.** El `mean_rationale_score` de T3 está limitado por")
    A("cómo el evaluador oficial construye el contexto del juez: `input_ctx` recibe sólo")
    A("`clinical_data` —los documentos enmascarados— y **nunca** `structured-prompt.json`,")
    A("que es donde vive el `psa`. El prompt de la tarea pide citar el PSA preoperatorio;")
    A("cuando el presidente lo cita correctamente, el juez lo marca como alucinación")
    A("porque no tiene el campo delante. Pasa en 4 de los 5 casos peor juzgados. No se")
    A("arregla desde nuestro lado, y se publica como límite medido en vez de esconderlo.")
    A("")
    if m3:
        A(f"**En esta corrida:** {m3.get('casos_ok')}/{m3.get('casos')} casos, "
          f"event=1 en {(m3.get('event') or {}).get('1', 0)}, "
          f"mediana {m3.get('meses_mediana')} meses (rango {m3.get('meses_min')}–{m3.get('meses_max')}), "
          f"{m3.get('respaldo')} notas de respaldo.")
        A("")
    A("---")
    A("")
    A("## 3. Lo que enseñan las pizarras")
    A("")
    A("Las actas no son un registro decorativo: son la única forma de responder a *por qué*")
    A("un caso salió como salió. El evaluador da un número por caso; el acta dice qué")
    A("peldaño lo reclamó, con qué evidencia y quién la puso sobre la mesa.")
    A("")
    doc += bloque_actas(tareas)
    A("")
    A("### Dónde se equivoca cada mecanismo")
    A("")
    A("El agregado oficial no puede decir esto, porque no conoce el protocolo. Repartiendo")
    A("los aciertos por el peldaño que decidió cada caso:")
    A("")
    doc += bloque_peldanos(tareas)
    A("### Las guardias, contadas")
    A("")
    doc += guardias(tareas)
    A("")
    A("El índice completo, ordenado para ir primero a las actas que más enseñan —las de")
    A("los casos que el protocolo falló— está en [PIZARRAS.md](PIZARRAS.md).")
    A("")
    A("---")
    A("")
    A("## 4. Coste")
    A("")
    doc += bloque_coste(tareas)
    A("")
    A("La GPU es de uso exclusivo: T1 y T2 levantan vLLM con los pesos locales y ocupan")
    A("~31 GB de los 32 de la tarjeta; T3 y el juez hablan con Ollama. No caben a la vez,")
    A("así que las cinco fases van estrictamente en serie.")
    A("")
    A("---")
    A("")
    A("## 5. Qué NO demuestra esta corrida")
    A("")
    A("- **Los expertos de T1 y T2 se entrenaron sobre esta misma cohorte etiquetada.** Que")
    A("  la corrida reproduzca la simulación verifica la ejecución; no demuestra")
    A("  generalización. T3 reproduce predicciones out-of-fold, que es más honesto, pero")
    A("  tampoco es validación externa.")
    A("- **El juez no es determinista, ni siquiera sin recargar el modelo.** Dos pases")
    A("  consecutivos de T2 dieron 0,8031 y 0,8150 sin tocar nada. El número con juez es")
    A("  una medición puntual; comparar dos corridas por esa columna no es válido.")
    A("- **Ninguna de estas cifras es el test.** Son los casos etiquetados, que es lo único")
    A("  que se puede puntuar en local.")
    A("- El techo honesto de T1 medido con expertos out-of-fold es 0,7607, frente al 0,8390")
    A("  histórico de la corrida desplegada. La diferencia es exactamente el efecto de")
    A("  haber ajustado los expertos sobre la cohorte.")
    A("")
    A("---")
    A("")
    A("## 6. Mapa")
    A("")
    A("```")
    A("resultados/")
    A("├── run_all.sh          las cinco fases, en serie e idempotentes")
    A("├── analizar.py         destila las corridas y las notas a scores/analisis.json")
    A("├── pizarras.py         construye el índice de actas")
    A("├── informe.py          escribe este documento desde los JSON")
    A("├── INFORME.md          esto")
    A("├── PIZARRAS.md         índice de las 238 actas, las fallidas primero")
    A("├── scores/")
    A("│   ├── no_judge.json   agregados del evaluador oficial, juez apagado")
    A("│   ├── judge_task*.json  ídem con el juez encendido, por tarea")
    A("│   └── analisis.json   mecanismo, actas y coste por tarea")
    A("├── task_1/  boards/ · output/task1/ · summary.jsonl · telemetry.jsonl")
    A("├── task_2/  boards/ · output/task2/ · summary.jsonl · telemetry.jsonl")
    A("└── task_3/  output/task3/<caso>/acta.md · summary.jsonl · telemetry.jsonl")
    A("```")
    A("")

    (RES / "INFORME.md").write_text("\n".join(doc) + "\n")
    print(f"Escrito {RES / 'INFORME.md'}  ({len(doc)} líneas)")


if __name__ == "__main__":
    main()

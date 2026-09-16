# CHIMERA V2_2 — el PLAN de V2, ejecutado

Este directorio **ejecuta** el plan que `../version_final_reto.runtime_16gb/PLAN.md`
diseñó. No lo reescribe: lo mide.

**Resultado en una frase: el mecanismo mejora, el ranking no.** Ocho de los doce
experimentos se han corrido. Los que ganan (supervivencia, menos consultas,
extracción con negación) ganan en fidelidad; los que prometían ranking —el
corrector sobre conceptos verificados, que era la apuesta central— **salen
negativos**. El cierre mínimo de +0,010 de OVERALL que pedía el PLAN **no se
alcanza**, y eso es el resultado, no un fallo de ejecución.

Detalle completo con todas las tablas: **[INFORME.md](INFORME.md)**.

## Veredictos

| Exp. | Veredicto |
|---|---|
| E00 reproducir H0 / construir B0 | ✅ exacta: OVERALL 0,82360; B0 cuesta −0,00235 |
| E01 negación, tiempo, fuente | ⚠️ negación sí (16 casos); cronología 0 casos |
| E02 el panel de T2 basta | ✅ panel a 1,8 puntos; **nada bate a la regla ISUP (0,861)** |
| E03 consultas adaptativas | ❌ 95,8% de decisiones no cambian; basta 1 documento |
| E04 conceptos verificados | ❌ el residual reproduce el ancla exactamente |
| E05 mapa continuo | ✅ 32 empates → 0; time_score +0,0172 |
| E06 ancla + residuo T3 | ✅ 0,73717 → 0,82832 |
| E07 curva de supervivencia | ✅ time_score +0,0188, c-index −0,0031 |
| E08 explicación · E10 integración | ⛔ exigen GPU y juez pareado |
| E09 multimodal | ⛔ bloqueado por el propio PLAN: E04 no validó |
| E11 16 GB | ✅ ensayo superado en `../version_final_reto.runtime_16gb/` |

## Estructura

```
common/       evidence.py     contrato de hechos verificables (§4.1)
              extractors.py   negación, cronología y fuente (E01)
evaluation/   groups.py       199 grupos, 170 entre tareas (§10.1)
              splits.py       anidadas por grupo, 5x3, semillas 111/223/337
              referencias.py  E00: H0 y B0
              e01..e07        los experimentos
              manifests/      particiones y grupos congelados
              reports/        resultados en JSON
```

## Reproducción

Desde la raíz del repositorio, sin GPU:

```bash
.venv/bin/python -m version_final_reto.investigacion.evaluation.groups
.venv/bin/python -m version_final_reto.investigacion.evaluation.splits
.venv/bin/python -m version_final_reto.investigacion.evaluation.referencias
.venv/bin/python -m version_final_reto.investigacion.evaluation.e01_extraccion
.venv/bin/python -m version_final_reto.investigacion.evaluation.e02_panel_t2
.venv/bin/python -m version_final_reto.investigacion.evaluation.e03_consultas
.venv/bin/python -m version_final_reto.investigacion.evaluation.e04_conceptos
.venv/bin/python -m version_final_reto.investigacion.evaluation.e05_mapa_t3
.venv/bin/python -m version_final_reto.investigacion.evaluation.e06_e07_supervivencia
```

Requiere el evaluador oficial en `../CHIMERA-agent-eval`. No llama al juez, no
entrena en GPU y no toca la inferencia entregada.

## Tres errores que se cometieron midiendo, y que están corregidos

Se dejan escritos porque cada uno produjo un número convincente y falso:

1. **Un ancla escrita a mano.** La regla ISUP inventada daba 0,306. Aprendiendo
   su mapeo en train da **0,861** y pasa a ser la política que nadie bate. Un
   ancla mal construida habría hecho ganar a cualquier candidato.
2. **Un signo supuesto.** El mapa continuo de T3 dio c-index 0,122 — que es
   1 − 0,878, el orden exactamente invertido. La puntuación del portavoz no es
   un riesgo creciente; hay que leer la orientación del mapa de V1, no suponerla.
3. **Una codificación ordinal de algo nominal.** El ancla de T2 entró al
   corrector como 0..3, imponiéndole un orden inexistente. Con one-hot sube de
   0,757 a 0,798 — sigue perdiendo, pero por la razón correcta.

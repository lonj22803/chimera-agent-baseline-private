# Lectura provisional del Tier S

Fecha: 2026-09-22. Modo primario: `honest`. Los veredictos aplican los margenes e IC del pre-registro; D exige ademas McNemar-Holm y signo DEV/VAL.

| H | Estado | Evidencia y regla | CSV | Desviaciones respecto a lo pre-registrado |
|---|---|---|---|---|
| H1 | **indeterminada** | S-COH: delta ranking 0.0648, IC95 [0.0186, 0.1142], McNemar-Holm p=0.5371; signo DEV/VAL positivo. Regla: `INDETERMINADA_D` | `S_loo.csv; S_robustez.csv` | Ninguna |
| H2 | **indeterminada** | S-M4: delta ranking 0.0302, IC95 [-0.0113, 0.0776], McNemar-Holm p=1; signos DEV/VAL opuestos. Regla: `INDETERMINADA_D` | `S_loo.csv; S_robustez.csv` | Ninguna |
| H3 | **indeterminada** | Voto honesto 15/27 frente a si constante 18/27; delta ranking A0-si -0.0829, IC95 [-0.2174, 0.0317]. Regla: `comparacion pareada del peldano de voto` | `S_cascade.csv` | Ninguna |
| H4 | **confirmada** | Shapley ranking E3=0.0371 y E1=-0.0052. Regla: `E1 < E3` | `S_factorial.csv` | Ninguna |
| H5 | **confirmada** | S-PSA-off: 0 filas distintas y delta cero en D, ranking y los cinco componentes. Regla: `SOBRA por construccion` | `S_loo.csv` | Ninguna |
| H6 | **confirmada** | Pesos constantes noted: delta ranking 0.0634. Abrir todo: delta tool 0.0818. Ambos brazos se clasifican NECESARIA_F. Regla: `pesos=NECESARIA_F; plan=NECESARIA_F` | `S_loo.csv; S_formulario.csv` | Ninguna |
| H7 | **refutada** | S-LIB-off: 0 filas distintas y delta cero en todos los componentes; no aparece la bajada F prevista. Regla: `SOBRA por construccion` | `S_loo.csv` | Ninguna |
| H8 | **indeterminada** | Cerrar radiologia cambia 3 decisiones y cerrar notas previas cambia 5, pero ninguna supera Holm; la equivalencia prosa-ejecutor requiere L0. Regla: `Tier L pendiente` | `S_loo.csv` | Ninguna |
| H15 | **confirmada** | Sin M11: variable_weight mejora 0.0378, grounding cae 0.1782 y el neto favorece a la guardia en 0.00833 de ranking. Regla: `NECESARIA_F` | `S_loo.csv; S_formulario.csv` | Ninguna |

## Lectura

Tier S sostiene con claridad la aportacion de E4 al formulario, la superioridad relativa de E3 sobre E1 y el valor neto de la guardia de aterrizaje. E2 es redundante por construccion y la biblioteca no produce el efecto F previsto. Cohorte y grado muestran efectos de magnitud relevante, pero el control Holm y, para grado, la falta de estabilidad DEV/VAL impiden llamarlos necesarios con la regla pre-registrada.

H8 no puede cerrarse sin L0: Tier S demuestra que los documentos pueden mover D, pero no mide si la prosa del registrador aporta algo frente a ejecutar el plan de forma determinista. Esta lectura no propone cambios de arquitectura.

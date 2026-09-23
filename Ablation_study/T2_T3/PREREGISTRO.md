# Preregistro operativo T2/T3

Fecha de congelacion: 2026-09-23. Este estudio es confirmatorio respecto al codigo actual, pero
retrospectivo respecto a los informes de expertos ya existentes. No se presenta como validacion
externa: los 72 casos T2 y los 75 T3 participaron en el desarrollo de parte de los artefactos.

## Pregunta

Que nodos pueden retirarse o colapsarse sin degradar la salida oficial, y que mecanismos deben
conservarse por decision, formulario, narrativa o integridad?

## Niveles

- `D`: ranking y decision multiclase en T2; c-index en T3.
- `F`: formulario T2; event y time en T3.
- `N`: `rationale_score` del juez oficial, tres pasadas en una residencia Ollama.
- `C`: segundos, llamadas y tokens cuando existan.

## Margenes y estadistica

- T2: `delta_rank=0.010`, `delta_decision=1/72`, `delta_F=0.010`.
- T3: `delta_cindex=0.020`, `delta_event=1/75`, `delta_time=0.020`.
- Narrativa: `delta_N=max(0.030, 2*EE entre las tres medias de pasada de la referencia)`.
- IC 95% por bootstrap pareado de 10.000 remuestreos, semilla `20260923`.
- Un cambio exactamente cero en todos los casos se declara equivalencia por construccion.
- `NECESARIA` exige que el IC quede sobre cero y el efecto supere el margen; `SOBRA` exige que
  el IC quede dentro del margen; en otro caso, `INDETERMINADA`.

## Hipotesis T2

- `T2-H1`: EXPERT-PATHOLOGY y EXPERT-FUSION son replicas; retirarlos juntos no cambia D/F.
- `T2-H2`: EXPERT-FITNESS afecta como maximo los tres casos donde habla y no supera el margen.
- `T2-H3`: EXPERT-CASCADE es necesario como respaldo cuando EXPERT-GRADE duda.
- `T2-H4`: EAU, MODERATOR y VERIFIER no tienen autoridad sobre D/F.
- `T2-H5`: un registrador determinista que abre el plan exacto sustituye al registrador LLM.
- `T2-H6`: la junta minima conserva D/F y reduce llamadas, tiempo y tokens.
- `T2-H7`: CHAIR solo afecta N; la nota determinista preserva D/F con una perdida N medible.

## Hipotesis T3

- `T3-H1`: el portavoz fusionado `selected` es necesario para ranking frente a CAPRA-S.
- `T3-H2`: EXPERT-SURGICAL, EXPERT-DIGITAL y EXPERT-FUSION pueden colapsarse en el unico motor
  ASGDE ya adoptado; sus turnos asesores no cambian la salida numerica.
- `T3-H3`: MODERATOR, REGISTRAR y VERIFIER pueden colapsarse en un digest determinista.
- `T3-H4`: EXPERT-HORIZON es necesario para event/time y para convertir orden en meses.
- `T3-H5`: CHAIR no mueve ranking, event ni time; solo N y `mean_case_score`.
- `T3-H6`: la arquitectura minima conserva exactamente los 75 pares `(event, months)`.

## Brazos GPU/juez

| Brazo | Tarea | Descripcion |
|---|---:|---|
| `T2-L0` | 2 | junta V4 completa |
| `T2-Lmin` | 2 | sin EAU/moderador/verificador LLM; registrador determinista; replicas removidas si CPU lo permite |
| `T2-Ldet` | 2 | D/F de `T2-Lmin`, nota clinica determinista |
| `T3-L0` | 3 | conferencia V4 actual, portavoz selected |
| `T3-Lmin` | 3 | motor ASGDE+horizonte, digest compacto y CHAIR |
| `T3-Ldet` | 3 | mismo motor numerico, nota determinista |

No se adopta ningun cambio en la V4. El resultado es una recomendacion y un prototipo reversible.

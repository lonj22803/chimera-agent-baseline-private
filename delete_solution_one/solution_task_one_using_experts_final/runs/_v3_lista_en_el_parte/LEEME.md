# Corrida con la LISTA CORTA de variables en el parte del presidente

195 casos, `ranking_score` 0.8390 — idéntico a las otras dos configuraciones,
porque decisión, confianza, pesos y revelaciones los fija el código y el juez de
razonamiento está apagado.

Es la segunda de las tres pruebas sobre **qué debe ver el presidente de la tabla
de variables**. Lo que se mide es si la nota entregada nombra las variables que
el formulario registra como motores (`important`/`decisive`):

| parte del presidente | recall | precisión | F1 | palabras |
|---|---|---|---|---|
| **sin bloque de variables** (`runs/final`) | **0.932** | 0.757 | **0.836** | 38 |
| la tabla entera (`_v2_tabla_en_el_parte`) | 0.890 | 0.760 | 0.820 | 38 |
| sólo la lista de variables (esta) | 0.900 | 0.733 | 0.808 | 39 |

Tres puntos, una dirección: darle al presidente la lista de variables **no** le
ayuda a nombrarlas. Le ayuda razonar sobre los hechos clínicos y llegar a ellas
solo. Un modelo de este tamaño gasta atención en cualquier lista que se le ponga
delante. Por eso la entrega no lleva bloque de variables en el parte, y la tabla
completa vive donde sí se usa: en el acta (intervención 13) y en el turno del
verificador, que la contesta variable por variable.

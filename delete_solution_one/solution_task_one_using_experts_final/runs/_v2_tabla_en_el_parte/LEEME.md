# Corrida con la tabla de variables ENTERA en el parte del presidente

195 casos, `ranking_score` 0.8390 — idéntico a la corrida sin tabla, porque la
decisión, la confianza, los pesos y las revelaciones ya los fija el código y el
juez de razonamiento está apagado.

Lo que sí cambió: **las 195 notas** (100 %). Y lo que se midió al compararlas:

| | sin tabla | con la tabla entera |
|---|---|---|
| variables registradas *important*/*decisive* que la nota nombra | **0.932** | 0.890 |
| variables nombradas que no están registradas así (ruido) | 0.26 | 0.28 |
| parte del presidente | ~1 200 caracteres | ~2 180 |
| tiempo por caso | 24 s | 32 s |

Conclusión, y por eso esta corrida queda archivada: darle al presidente la tabla
entera **no** mejora la nota, la empeora un poco. Un modelo de este tamaño no
necesita más material sino la lista corta de lo que tiene que nombrar. La
entrega usa esa lista; la tabla completa sigue en el acta (intervención 13), que
es donde la sala la usa para discutir.

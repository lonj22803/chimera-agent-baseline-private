# result_v2 — cobertura completa de V2_2 y comparativa

**12 de septiembre de 2026.** 423 casos ejecutados, 423 pizarras, 3 h 18 min de
GPU. Puntuado con el evaluador oficial, juez apagado.

## Lo que se ejecutó

V2_2 = la imagen V2 (perfil de 16 GB) **más un solo cambio**: el exportador de
meses de T3 pasa del percentil por CDF empírica a una CDF normal congelada en
train. T1 y T2 son los de la V1.1 sin tocar, porque E04 concluyó que el
corrector sobre conceptos verificados no aporta señal.

| Tarea | Segundos | Salidas | Pizarras |
|---|---:|---:|---:|
| 3 — recurrencia | 301 | 75 | 75 actas (11 intervenciones cada una) |
| 1 — biopsia | 5 129 | 195 (91 + 104) | 195 |
| 2 — tratamiento | 6 418 | 153 (72 + 81) | 153 |
| **total** | **11 848** | **423** | **423** |

Las pizarras están en `task_N/boards/<caso>.json` y `.md` para las tres tareas.
Las de T3 las escribe su runner como `acta.json`/`acta.md` junto a la salida de
cada caso; el cierre las copia a `boards/` para que las tres se busquen igual.
Los originales siguen donde los dejó el runner.

## Comparativa

| referencia | T1 | T2 | T3 | OVERALL |
|---|---:|---:|---:|---:|
| **H0** (V1 histórica) | 0,83903 | 0,77839 | 0,88319 | **0,82360** |
| **B0** (traza corregida) | 0,83903 | 0,77252 | 0,88319 | **0,82126** |
| **V2_2** (esta corrida) | 0,83903 | 0,77839 | 0,88319 | **0,82360** |

**V2_2 iguala H0 al quinto decimal: Δ +0,00000.**

Y eso es exactamente lo que tenía que pasar. No es un resultado decepcionante
por accidente: es la consecuencia aritmética de los veredictos de los
experimentos.

- **T1 y T2 no cambian** porque E04 salió negativo y no había nada que cambiar.
- **El c-index de T3 no cambia** porque el exportador nuevo es **estrictamente
  monótono**: conserva el orden del riesgo, y el c-index sólo mira el orden. Que
  salga idéntico es la prueba de que funciona como se diseñó, no de que no haga
  nada.

### El +0,00235 sobre B0 no es una mejora

V2_2 puntúa por encima de B0 porque **hereda el mismo problema de traza**: sigue
declarando `reveal_sequence: []` en los 72 casos de T2 mientras abre seis
secciones. B0 es la referencia honesta; V2_2 no la ha corregido. Leer ese
+0,00235 como ganancia sería leer al revés lo que mide.

## Lo que sí cambió en T3, y no se ve en el ranking

Los 75 casos exportan meses distintos, con el mismo orden:

| exportador | c-index | time_score | empates | rango |
|---|---:|---:|---:|---|
| V1, CDF empírica | 0,88319 | 0,72018 | **12** | [27,3 · 88,6] |
| **V2_2, CDF suave** | **0,88319** | **0,72964** | **0** | [27,1 · 87,6] |

`time_score` **+0,00946** y los 12 empates eliminados. El rango no se ha tocado:
`a`, `b` y `risk_scale` siguen siendo los de V1, porque elegir un rango nuevo
por su nota en estos mismos 75 casos sería ajuste dentro de muestra, que el PLAN
§10.5 prohíbe.

Cada acta de T3 registra la sustitución de forma auditable: el exportador usado,
qué reemplaza, y **el valor que habría dado la CDF empírica** al lado del nuevo.
Así se puede comparar caso a caso sin volver a correr nada.

## Dos avisos que hay que leer con la tabla

**1. Cobertura es contrato, no calidad.** De los 423 casos sólo 238 tienen
etiqueta, y los expertos de T1 y T2 se ajustaron sobre esas mismas cohortes.
Ninguna cifra de aquí es una estimación fuera de muestra. Los números honestos
están en los experimentos: techo de T1 fuera de muestra 0,7607 frente al 0,8390
de aquí; c-index de T3 defendible 0,8235 frente al 0,8832 de aquí.

**2. Esta corrida NO valida el perfil de 16 GB.** Usa el tope de 19 GiB de la
V1.1 y su pico fue de 21 502 MiB. Es deliberado: un lote caliente de 195 casos
en un proceso no reproduce el arranque frío por paciente de Grand Challenge. El
perfil se valida con la compuerta sin montar de
`../delete_final_versions_task_V2/`, que dio 13 332 MiB.

## Contenido del directorio

```
task_1/{labeled,unlabeled}/{output,boards}   195 salidas + 195 pizarras
task_2/{labeled,unlabeled}/{output,boards}   153 salidas + 153 pizarras
task_3/output/task3/<caso>/                   75 salidas + acta.json/.md
task_3/boards/                                copia de las 75 actas
task_3_primera_pasada/                        primera corrida de T3: meses idénticos,
                                              acta con los parámetros heredados mal
comparativa.json                              todo lo anterior más los 7 experimentos
cobertura_resumen.json                        hashes de V2_2, comandos, tiempos
task{1,2,3}.log                               log completo de cada contenedor
```

`task_3_primera_pasada/` se conserva a propósito: sus meses son idénticos a los
de la corrida final —el mapa siempre usó `a=90`—, pero su acta declaraba
`a=93,67`, heredado de la rama original. Un acta que declara parámetros
distintos de los aplicados no sirve como evidencia, y dejar las dos permite
comprobar que lo único que cambió fue el registro.

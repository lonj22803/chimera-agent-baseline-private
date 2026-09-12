# CHIMERA — versión final del reto

Lo que se entrega. Todo lo demás se retiró de `main` el 12-sep-2026 y vive en la
rama **`pre-limpieza`**, que conserva el repositorio entero tal como estaba.

## Qué es

Una **junta clínica** por tarea: expertos entrenados que aportan un número, un
protocolo reproducible que decide, y un LLM que **redacta y no vota**. Sobre eso,
dos correcciones operativas medidas en `investigacion/`.

| Tarea | Decide | Pizarra |
|---|---|---|
| 1 — biopsia | cascada de reglas sobre expertos entrenados | sí |
| 2 — tratamiento | cascada de guía clínica, 4 clases | sí |
| 3 — recurrencia | portavoz seleccionado de forma anidada + exportador | sí, 11 intervenciones |

## Por dónde empezar

| Quiero… | Leer |
|---|---|
| La arquitectura de conjunto | [ARQUITECTURA.md](ARQUITECTURA.md) |
| **Los expertos de T1 y por qué cada uno** | [README_TAREA_1_EXPERTOS_ARQUITECTURA.md](README_TAREA_1_EXPERTOS_ARQUITECTURA.md) · [task_1/README.md](task_1/README.md) |
| Los expertos de T2 | [task_2/README.md](task_2/README.md) |
| Los cinco expertos de T3 y el portavoz | [task_3/README.md](task_3/README.md) · [task_3/experts_3/README.md](task_3/experts_3/README.md) |
| Los prompts de cada junta | [task_1/PROMPTS.md](task_1/PROMPTS.md) · [task_2/PROMPTS.md](task_2/PROMPTS.md) · [task_3/PROMPTS.md](task_3/PROMPTS.md) |
| **Dónde está cada pizarra** | [PIZARRAS.md](PIZARRAS.md) |
| Cómo se llegó hasta aquí | [BITACORA.md](BITACORA.md) · [BITACORA_V1_1.md](BITACORA_V1_1.md) |
| El plan que guio el trabajo | [PLAN.md](PLAN.md) |
| Qué comprobar antes de enviar | [ENTREGA_CHECKLIST.md](ENTREGA_CHECKLIST.md) · [ENTREGA.md](ENTREGA.md) |
| El perfil de 16 GB | [runtime_16gb/](runtime_16gb/) |
| **Qué se probó y qué falló** | [investigacion/INFORME.md](investigacion/INFORME.md) |
| Los resultados sobre los 423 casos | [../result_v2/RESULTADOS.md](../result_v2/RESULTADOS.md) |

## Estructura

```
version_final_reto/
  common/              pizarra, contrato de salida, expertos compartidos,
                       telemetría, reloj de Grand Challenge, guardias
  task_1/  task_2/     agente, grafo, prompts, expertos entrenados y su
  task_3/              entrenamiento; cada uno con su README y sus análisis
  runtime_16gb/        perfil de memoria de §13.1: 21 502 -> 13 332 MiB
  investigacion/       los 8 experimentos ejecutados del PLAN de V2, sus
                       veredictos, y el exportador de T3 que salió de ellos
  verification/        compuertas: cobertura, perfilado, contrato, respaldos
  experiments/         análisis históricos que sustentan las decisiones
  inference_final.py   el entrypoint del contenedor
```

## Cómo se ejecuta

```bash
./do_build_final.sh                    # construye chimera_agent_baseline_final
./do_save_final.sh                     # empaqueta imagen + modelo para subir

# La compuerta: la imagen tal cual, sin montar código
python3 version_final_reto/verification/gc_profile.py \
    --cpuset 0-3 --interfaces 0,1,2 --image chimera_agent_baseline_final --no-mount
```

El modelo (`model/`) y los datos (`data/`) no están en el repositorio: pesan
19 GB y el segundo está bajo acuerdo de uso.

## Qué cambió respecto a lo entregado en V1

Dos cosas, y ninguna toca una decisión clínica:

1. **El perfil de memoria.** El KV dejó de dimensionarse por «lo que sobre en la
   tarjeta» y pasa a dimensionarse por lo que un paciente necesita. Pico de
   21 502 a **13 332 MiB**, sin recortar el contexto de 32 768, sin cuantizar y
   sin quitar ningún experto. Permite correr en una GPU de 16 GB, donde la
   versión anterior **no arranca**.
2. **El exportador de T3.** El percentil por CDF empírica —75 valores, hasta 76
   escalones— se sustituye por una CDF normal congelada en train, estrictamente
   creciente. c-index **idéntico**, `time_score` +0,0095, **12 empates → 0**.

Lo medido de punta a punta sobre los 423 casos está en
[../result_v2/RESULTADOS.md](../result_v2/RESULTADOS.md): **OVERALL 0,82360, el
mismo que V1**. Las ganancias son de fidelidad, y el evaluador no las premia.
Decirlo así es parte del resultado.

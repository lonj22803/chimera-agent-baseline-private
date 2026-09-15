# CHIMERA V2: plan de una junta que investiga qué cambiaría su decisión

**Estado: diseño, con una fase implementada y medida. 11–12 de septiembre de 2026.**
El PLAN sigue siendo diseño: las mejoras de decisión (fases B a E) están por implementar y ninguna mejora de resultados está demostrada. Lo que sí existe y está medido es el **perfil de memoria de §13.1 (E11)**.

**Requisito obligatorio:** arquitectura completa en una sola GPU de 16 GB y hasta 32 GiB RAM.

> **E11, ensayo preliminar superado.** Con la tarjeta recortada a 16 GiB, el perfil de la V1.1 **no arranca el motor** (pide 19 GiB) y todos los casos caerían al respaldo. El perfil de V2 arranca y completa las **tres interfaces en contenedor, sin montar código**, con un pico neto de **13 332 MiB** bajo el techo de 14 336, conservando contexto 32 768, precisión bf16 y todos los expertos. **Las seis salidas son byte a byte idénticas** a la referencia V1.1 con el mismo `case_id`. Coste temporal: neutral.
>
> No hizo falta ni `cpu_offload_gb`, ni recortar contexto, ni cuantizar: sobraba KV reservado, no faltaba memoria.
>
> **Estado: pendiente de validación física** — el recorte es por lastre en una RTX 5090, no una GPU de 16 GB identificada.
>
> Detalle: [evaluation/reports/resources_16gb/INFORME.md](evaluation/reports/resources_16gb/INFORME.md) y [BITACORA_V2.md](BITACORA_V2.md).

**Advertencia sobre el diagnóstico:** el rechazo de Development del 10-sep fue por **tiempo**, no por memoria; el `31.59x` de su propio log prueba que había una A10G de 24 GiB con VRAM de sobra. Este perfil es requisito del PLAN y desbloquea tarjetas pequeñas, pero **no cierra el límite temporal**.

La propuesta conserva la pizarra, los especialistas, el protocolo reproducible y el presidente. Cambia el trabajo de la junta: los especialistas construyen hechos clínicos verificables, el protocolo identifica las dudas que pueden cambiar una decisión y se consultan únicamente las fuentes necesarias para resolverlas. Una corrección aprendida y acotada puede mejorar V1; una conversación más larga, por sí sola, no puede cambiar el resultado.

- [PLAN.md](PLAN.md): diseño completo, tareas, experimentos, criterios de adopción y entrega.
- [EVIDENCIA.md](EVIDENCIA.md): qué dicen realmente V1 y los experimentos anteriores; auditoría nueva y fuentes consultadas.
- [analisis/auditoria_base.json](analisis/auditoria_base.json): mediciones descriptivas y hashes de los artefactos de partida.
- [analisis/auditar_base.py](analisis/auditar_base.py): reproducción de esa auditoría sin GPU, entrenamiento ni llamadas al juez.

La prioridad es **mejorar la representación y la adquisición de evidencia**, después la decisión y finalmente su explicación. No se promete superar una cifra antes de medir el sistema completo fuera de muestra. La auditoría ya identifica problemas concretos que justifican este cambio de arquitectura.

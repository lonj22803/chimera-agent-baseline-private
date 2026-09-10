# Las pizarras, caso por caso

Cada junta deja un acta: una intervención por turno, numeradas de forma global
y monótona, con lo que dijo cada participante literalmente y lo que el código
calculó de ese turno. Es la traza de cómo se enfrentó el problema, no un resumen
escrito después. Están en `task_N/boards/<caso>.{md,json}` (tareas 1 y 2) y en
`task_3/output/task3/<caso>/acta.{md,json}` (tarea 3).

Este índice existe para saber a cuál ir. Los casos se listan **primero los que
el protocolo falló**, luego los que el verificador reabrió o acabaron en respaldo,
y después el resto por orden de caso.

## Tarea 1 · decisión de biopsia

91 actas. 8 decisiones contra la referencia, 1 con reapertura o respaldo.

### Donde el protocolo se equivocó (8)

Son las actas que más enseñan: el mecanismo está escrito y se ve qué peldaño disparó y con qué evidencia.

| caso | acta | peldaño | decisión | referencia | ✓ | int. |
|---|---|---|---|---|---|---|
| `PT-pseudo_0169468160c6` | [acta](task_1/boards/PT-pseudo_0169468160c6.md) | 1 · criterio de cohorte | no | yes | **✗** | 14 |
| `PT-pseudo_175e6ad47991` | [acta](task_1/boards/PT-pseudo_175e6ad47991.md) | 1 · criterio de cohorte | yes | no | **✗** | 14 |
| `PT-pseudo_1dc32184cab6` | [acta](task_1/boards/PT-pseudo_1dc32184cab6.md) | 1 · criterio de cohorte | yes | no | **✗** | 14 |
| `PT-pseudo_37d8ae9b27f1` | [acta](task_1/boards/PT-pseudo_37d8ae9b27f1.md) | 3 · voto ponderado | yes | no | **✗** | 14 |
| `PT-pseudo_3b6ea1920967` | [acta](task_1/boards/PT-pseudo_3b6ea1920967.md) | 3 · voto ponderado | yes | no | **✗** | 14 |
| `PT-pseudo_b9f0b7018502` | [acta](task_1/boards/PT-pseudo_b9f0b7018502.md) | 2 · grado documentado | no | yes | **✗** | 14 |
| `PT-pseudo_d217629c323a` | [acta](task_1/boards/PT-pseudo_d217629c323a.md) | 3 · voto ponderado | yes | no | **✗** | 14 |
| `PT-pseudo_d7d26761c714` | [acta](task_1/boards/PT-pseudo_d7d26761c714.md) | 2 · grado documentado | yes | no | **✗** | 14 |

### Reaperturas y respaldos (1)

| caso | acta | peldaño | decisión | referencia | ✓ | int. |
|---|---|---|---|---|---|---|
| `PT-pseudo_2eef4115a253` | [acta](task_1/boards/PT-pseudo_2eef4115a253.md) | 1 · criterio de cohorte | yes | yes | ✓ | 14 |

<details><summary>Los 82 restantes</summary>

| caso | acta | peldaño | decisión | referencia | ✓ | int. |
|---|---|---|---|---|---|---|
| `PT-pseudo_0020cfca66c8` | [acta](task_1/boards/PT-pseudo_0020cfca66c8.md) | 1 · criterio de cohorte | no | no | ✓ | 14 |
| `PT-pseudo_01b643727538` | [acta](task_1/boards/PT-pseudo_01b643727538.md) | 2 · grado documentado | no | no | ✓ | 14 |
| `PT-pseudo_033f1a8e1503` | [acta](task_1/boards/PT-pseudo_033f1a8e1503.md) | 1 · criterio de cohorte | yes | yes | ✓ | 14 |
| `PT-pseudo_0615b2bd8504` | [acta](task_1/boards/PT-pseudo_0615b2bd8504.md) | 1 · criterio de cohorte | no | no | ✓ | 14 |
| `PT-pseudo_062a1125899d` | [acta](task_1/boards/PT-pseudo_062a1125899d.md) | 1 · criterio de cohorte | yes | yes | ✓ | 14 |
| `PT-pseudo_06b319f42fcb` | [acta](task_1/boards/PT-pseudo_06b319f42fcb.md) | 2 · grado documentado | yes | yes | ✓ | 14 |
| `PT-pseudo_075dd468b384` | [acta](task_1/boards/PT-pseudo_075dd468b384.md) | 3 · voto ponderado | yes | yes | ✓ | 14 |
| `PT-pseudo_079636ac5644` | [acta](task_1/boards/PT-pseudo_079636ac5644.md) | 2 · grado documentado | no | no | ✓ | 14 |
| `PT-pseudo_0930885168c9` | [acta](task_1/boards/PT-pseudo_0930885168c9.md) | 3 · voto ponderado | yes | yes | ✓ | 14 |
| `PT-pseudo_099651db404e` | [acta](task_1/boards/PT-pseudo_099651db404e.md) | 1 · criterio de cohorte | yes | yes | ✓ | 14 |
| `PT-pseudo_0bd72f429a8b` | [acta](task_1/boards/PT-pseudo_0bd72f429a8b.md) | 3 · voto ponderado | yes | yes | ✓ | 14 |
| `PT-pseudo_0cdfb9410718` | [acta](task_1/boards/PT-pseudo_0cdfb9410718.md) | 3 · voto ponderado | yes | yes | ✓ | 14 |
| `PT-pseudo_0de7e606ca70` | [acta](task_1/boards/PT-pseudo_0de7e606ca70.md) | 1 · criterio de cohorte | yes | yes | ✓ | 14 |
| `PT-pseudo_11345b8a7ab3` | [acta](task_1/boards/PT-pseudo_11345b8a7ab3.md) | 1 · criterio de cohorte | no | no | ✓ | 14 |
| `PT-pseudo_11574b12444b` | [acta](task_1/boards/PT-pseudo_11574b12444b.md) | 1 · criterio de cohorte | yes | yes | ✓ | 14 |
| `PT-pseudo_1185f6a68df0` | [acta](task_1/boards/PT-pseudo_1185f6a68df0.md) | 1 · criterio de cohorte | yes | yes | ✓ | 14 |
| `PT-pseudo_11fe9c6ca833` | [acta](task_1/boards/PT-pseudo_11fe9c6ca833.md) | 1 · criterio de cohorte | no | no | ✓ | 14 |
| `PT-pseudo_132e0000c0e0` | [acta](task_1/boards/PT-pseudo_132e0000c0e0.md) | 1 · criterio de cohorte | yes | yes | ✓ | 14 |
| `PT-pseudo_138092c2a6be` | [acta](task_1/boards/PT-pseudo_138092c2a6be.md) | 3 · voto ponderado | yes | yes | ✓ | 14 |
| `PT-pseudo_152344add0f1` | [acta](task_1/boards/PT-pseudo_152344add0f1.md) | 1 · criterio de cohorte | yes | yes | ✓ | 14 |
| `PT-pseudo_17f110c9e142` | [acta](task_1/boards/PT-pseudo_17f110c9e142.md) | 2 · grado documentado | no | no | ✓ | 14 |
| `PT-pseudo_180352970ace` | [acta](task_1/boards/PT-pseudo_180352970ace.md) | 1 · criterio de cohorte | yes | yes | ✓ | 14 |
| `PT-pseudo_1a4e0cf3b927` | [acta](task_1/boards/PT-pseudo_1a4e0cf3b927.md) | 2 · grado documentado | no | no | ✓ | 14 |
| `PT-pseudo_20a7e91c494c` | [acta](task_1/boards/PT-pseudo_20a7e91c494c.md) | 3 · voto ponderado | no | no | ✓ | 14 |
| `PT-pseudo_20ba3f0f6ca0` | [acta](task_1/boards/PT-pseudo_20ba3f0f6ca0.md) | 1 · criterio de cohorte | yes | yes | ✓ | 14 |
| `PT-pseudo_21e7fa67a79e` | [acta](task_1/boards/PT-pseudo_21e7fa67a79e.md) | 3 · voto ponderado | yes | yes | ✓ | 14 |
| `PT-pseudo_249def42388a` | [acta](task_1/boards/PT-pseudo_249def42388a.md) | 1 · criterio de cohorte | yes | yes | ✓ | 14 |
| `PT-pseudo_25007bb807d7` | [acta](task_1/boards/PT-pseudo_25007bb807d7.md) | 1 · criterio de cohorte | yes | yes | ✓ | 14 |
| `PT-pseudo_259484ae733f` | [acta](task_1/boards/PT-pseudo_259484ae733f.md) | 3 · voto ponderado | yes | yes | ✓ | 14 |
| `PT-pseudo_2b3ef1d3a505` | [acta](task_1/boards/PT-pseudo_2b3ef1d3a505.md) | 3 · voto ponderado | no | no | ✓ | 14 |
| `PT-pseudo_2cd88bcdf81c` | [acta](task_1/boards/PT-pseudo_2cd88bcdf81c.md) | 1 · criterio de cohorte | yes | yes | ✓ | 14 |
| `PT-pseudo_2e0346bce3b3` | [acta](task_1/boards/PT-pseudo_2e0346bce3b3.md) | 3 · voto ponderado | yes | yes | ✓ | 14 |
| `PT-pseudo_2e4988b84112` | [acta](task_1/boards/PT-pseudo_2e4988b84112.md) | 1 · criterio de cohorte | no | no | ✓ | 14 |
| `PT-pseudo_2ef22b5dd08e` | [acta](task_1/boards/PT-pseudo_2ef22b5dd08e.md) | 1 · criterio de cohorte | yes | yes | ✓ | 14 |
| `PT-pseudo_2fbb84505a45` | [acta](task_1/boards/PT-pseudo_2fbb84505a45.md) | 2 · grado documentado | yes | yes | ✓ | 14 |
| `PT-pseudo_33c8cd4571fd` | [acta](task_1/boards/PT-pseudo_33c8cd4571fd.md) | 1 · criterio de cohorte | yes | yes | ✓ | 14 |
| `PT-pseudo_34647958aba3` | [acta](task_1/boards/PT-pseudo_34647958aba3.md) | 3 · voto ponderado | no | no | ✓ | 14 |
| `PT-pseudo_3477ea7065bd` | [acta](task_1/boards/PT-pseudo_3477ea7065bd.md) | 1 · criterio de cohorte | yes | yes | ✓ | 14 |
| `PT-pseudo_3646e0a2ae13` | [acta](task_1/boards/PT-pseudo_3646e0a2ae13.md) | 1 · criterio de cohorte | no | no | ✓ | 14 |
| `PT-pseudo_36c92fb424ac` | [acta](task_1/boards/PT-pseudo_36c92fb424ac.md) | 1 · criterio de cohorte | yes | yes | ✓ | 14 |
| `PT-pseudo_376de00c8131` | [acta](task_1/boards/PT-pseudo_376de00c8131.md) | 1 · criterio de cohorte | yes | yes | ✓ | 14 |
| `PT-pseudo_394e0b8dbeeb` | [acta](task_1/boards/PT-pseudo_394e0b8dbeeb.md) | 1 · criterio de cohorte | yes | yes | ✓ | 14 |
| `PT-pseudo_3cc88c81f35a` | [acta](task_1/boards/PT-pseudo_3cc88c81f35a.md) | 1 · criterio de cohorte | no | no | ✓ | 14 |
| `PT-pseudo_3ceacc9b660b` | [acta](task_1/boards/PT-pseudo_3ceacc9b660b.md) | 3 · voto ponderado | no | no | ✓ | 14 |
| `PT-pseudo_3f75ae876abe` | [acta](task_1/boards/PT-pseudo_3f75ae876abe.md) | 1 · criterio de cohorte | yes | yes | ✓ | 14 |
| `PT-pseudo_41ca49bed13d` | [acta](task_1/boards/PT-pseudo_41ca49bed13d.md) | 1 · criterio de cohorte | yes | yes | ✓ | 14 |
| `PT-pseudo_47c373e230b6` | [acta](task_1/boards/PT-pseudo_47c373e230b6.md) | 3 · voto ponderado | yes | yes | ✓ | 14 |
| `PT-pseudo_47d8b39fd07f` | [acta](task_1/boards/PT-pseudo_47d8b39fd07f.md) | 1 · criterio de cohorte | no | no | ✓ | 14 |
| `PT-pseudo_48fb60dfd22f` | [acta](task_1/boards/PT-pseudo_48fb60dfd22f.md) | 1 · criterio de cohorte | yes | yes | ✓ | 14 |
| `PT-pseudo_4a2fa7bc3595` | [acta](task_1/boards/PT-pseudo_4a2fa7bc3595.md) | 3 · voto ponderado | yes | yes | ✓ | 14 |
| `PT-pseudo_4a4fedfc1f51` | [acta](task_1/boards/PT-pseudo_4a4fedfc1f51.md) | 1 · criterio de cohorte | yes | yes | ✓ | 14 |
| `PT-pseudo_4b950525e6a8` | [acta](task_1/boards/PT-pseudo_4b950525e6a8.md) | 2 · grado documentado | no | no | ✓ | 14 |
| `PT-pseudo_4bfd4ec864d8` | [acta](task_1/boards/PT-pseudo_4bfd4ec864d8.md) | 1 · criterio de cohorte | yes | yes | ✓ | 14 |
| `PT-pseudo_4c6b2b2bbf94` | [acta](task_1/boards/PT-pseudo_4c6b2b2bbf94.md) | 3 · voto ponderado | no | no | ✓ | 14 |
| `PT-pseudo_4d54f04e26ae` | [acta](task_1/boards/PT-pseudo_4d54f04e26ae.md) | 1 · criterio de cohorte | yes | yes | ✓ | 14 |
| `PT-pseudo_4e545d350c5b` | [acta](task_1/boards/PT-pseudo_4e545d350c5b.md) | 1 · criterio de cohorte | yes | yes | ✓ | 14 |
| `PT-pseudo_4edb17f79e46` | [acta](task_1/boards/PT-pseudo_4edb17f79e46.md) | 1 · criterio de cohorte | yes | yes | ✓ | 14 |
| `PT-pseudo_4f33b0253633` | [acta](task_1/boards/PT-pseudo_4f33b0253633.md) | 1 · criterio de cohorte | no | no | ✓ | 14 |
| `PT-pseudo_52213169f58b` | [acta](task_1/boards/PT-pseudo_52213169f58b.md) | 1 · criterio de cohorte | yes | yes | ✓ | 14 |
| `PT-pseudo_562159dc2cc6` | [acta](task_1/boards/PT-pseudo_562159dc2cc6.md) | 1 · criterio de cohorte | no | no | ✓ | 14 |
| `PT-pseudo_575cb2819e96` | [acta](task_1/boards/PT-pseudo_575cb2819e96.md) | 1 · criterio de cohorte | yes | yes | ✓ | 14 |
| `PT-pseudo_590e7b237744` | [acta](task_1/boards/PT-pseudo_590e7b237744.md) | 1 · criterio de cohorte | no | no | ✓ | 14 |
| `PT-pseudo_b9aa0df93f2a` | [acta](task_1/boards/PT-pseudo_b9aa0df93f2a.md) | 3 · voto ponderado | yes | yes | ✓ | 14 |
| `PT-pseudo_c03b1168ff4d` | [acta](task_1/boards/PT-pseudo_c03b1168ff4d.md) | 3 · voto ponderado | yes | yes | ✓ | 14 |
| `PT-pseudo_c12bcf838ec8` | [acta](task_1/boards/PT-pseudo_c12bcf838ec8.md) | 1 · criterio de cohorte | no | no | ✓ | 14 |
| `PT-pseudo_c13fda040310` | [acta](task_1/boards/PT-pseudo_c13fda040310.md) | 1 · criterio de cohorte | yes | yes | ✓ | 14 |
| `PT-pseudo_c39e94a13920` | [acta](task_1/boards/PT-pseudo_c39e94a13920.md) | 3 · voto ponderado | yes | yes | ✓ | 14 |
| `PT-pseudo_c55496c11421` | [acta](task_1/boards/PT-pseudo_c55496c11421.md) | 1 · criterio de cohorte | no | no | ✓ | 14 |
| `PT-pseudo_c7277954c60f` | [acta](task_1/boards/PT-pseudo_c7277954c60f.md) | 1 · criterio de cohorte | no | no | ✓ | 14 |
| `PT-pseudo_c9d31197c533` | [acta](task_1/boards/PT-pseudo_c9d31197c533.md) | 2 · grado documentado | no | no | ✓ | 14 |
| `PT-pseudo_cac2563c222a` | [acta](task_1/boards/PT-pseudo_cac2563c222a.md) | 2 · grado documentado | yes | yes | ✓ | 14 |
| `PT-pseudo_cce5d47c05dd` | [acta](task_1/boards/PT-pseudo_cce5d47c05dd.md) | 2 · grado documentado | no | no | ✓ | 14 |
| `PT-pseudo_d38917f87b35` | [acta](task_1/boards/PT-pseudo_d38917f87b35.md) | 1 · criterio de cohorte | no | no | ✓ | 14 |
| `PT-pseudo_d3d6b421d0aa` | [acta](task_1/boards/PT-pseudo_d3d6b421d0aa.md) | 3 · voto ponderado | yes | yes | ✓ | 14 |
| `PT-pseudo_d3e975d025e6` | [acta](task_1/boards/PT-pseudo_d3e975d025e6.md) | 1 · criterio de cohorte | yes | yes | ✓ | 14 |
| `PT-pseudo_d49b896a09e6` | [acta](task_1/boards/PT-pseudo_d49b896a09e6.md) | 3 · voto ponderado | yes | yes | ✓ | 14 |
| `PT-pseudo_d5ceb6b4204f` | [acta](task_1/boards/PT-pseudo_d5ceb6b4204f.md) | 3 · voto ponderado | yes | yes | ✓ | 14 |
| `PT-pseudo_d95b3a02898e` | [acta](task_1/boards/PT-pseudo_d95b3a02898e.md) | 1 · criterio de cohorte | no | no | ✓ | 14 |
| `PT-pseudo_dcd61cf9b443` | [acta](task_1/boards/PT-pseudo_dcd61cf9b443.md) | 3 · voto ponderado | no | no | ✓ | 14 |
| `PT-pseudo_dcd7bf13a6f4` | [acta](task_1/boards/PT-pseudo_dcd7bf13a6f4.md) | 1 · criterio de cohorte | yes | yes | ✓ | 14 |
| `PT-pseudo_dd011d696387` | [acta](task_1/boards/PT-pseudo_dd011d696387.md) | 3 · voto ponderado | yes | yes | ✓ | 14 |
| `PT-pseudo_e001f4d06517` | [acta](task_1/boards/PT-pseudo_e001f4d06517.md) | 3 · voto ponderado | yes | yes | ✓ | 14 |

</details>

## Tarea 2 · decisión de tratamiento

72 actas. 7 decisiones contra la referencia, 3 con reapertura o respaldo.

### Donde el protocolo se equivocó (7)

Son las actas que más enseñan: el mecanismo está escrito y se ve qué peldaño disparó y con qué evidencia.

| caso | acta | peldaño | decisión | referencia | ✓ | int. |
|---|---|---|---|---|---|---|
| `T2-008` | [acta](task_2/boards/T2-008.md) | expert_one | active_treatment | active_surveillance | **✗** | 12 |
| `T2-011` | [acta](task_2/boards/T2-011.md) | expert_one | active_treatment | active_surveillance | **✗** | 12 |
| `T2-018` | [acta](task_2/boards/T2-018.md) | expert_one | continued_surveillance | active_surveillance | **✗** | 12 |
| `T2-031` | [acta](task_2/boards/T2-031.md) | expert_one | active_treatment | watchful_waiting | **✗** | 12 |
| `T2-032` | [acta](task_2/boards/T2-032.md) | expert_one | active_treatment | watchful_waiting | **✗** | 12 |
| `T2-043` | [acta](task_2/boards/T2-043.md) | expert_one | active_surveillance | active_treatment | **✗** | 12 |
| `T2-108` | [acta](task_2/boards/T2-108.md) | expert_one | active_surveillance | continued_surveillance | **✗** | 12 |

### Reaperturas y respaldos (3)

| caso | acta | peldaño | decisión | referencia | ✓ | int. |
|---|---|---|---|---|---|---|
| `T2-005` | [acta](task_2/boards/T2-005.md) | expert_one | active_surveillance | active_surveillance | ✓ | 12 |
| `T2-010` | [acta](task_2/boards/T2-010.md) | expert_one | active_surveillance | active_surveillance | ✓ | 12 |
| `T2-051` | [acta](task_2/boards/T2-051.md) | expert_one | continued_surveillance | continued_surveillance | ✓ | 12 |

<details><summary>Los 62 restantes</summary>

| caso | acta | peldaño | decisión | referencia | ✓ | int. |
|---|---|---|---|---|---|---|
| `T2-001` | [acta](task_2/boards/T2-001.md) | expert_one | active_surveillance | active_surveillance | ✓ | 12 |
| `T2-002` | [acta](task_2/boards/T2-002.md) | expert_one | active_treatment | active_treatment | ✓ | 12 |
| `T2-003` | [acta](task_2/boards/T2-003.md) | expert_one | active_treatment | active_treatment | ✓ | 12 |
| `T2-004` | [acta](task_2/boards/T2-004.md) | expert_one | active_treatment | active_treatment | ✓ | 12 |
| `T2-006` | [acta](task_2/boards/T2-006.md) | expert_one | active_surveillance | active_surveillance | ✓ | 12 |
| `T2-007` | [acta](task_2/boards/T2-007.md) | expert_one | active_treatment | active_treatment | ✓ | 12 |
| `T2-009` | [acta](task_2/boards/T2-009.md) | expert_one | active_surveillance | active_surveillance | ✓ | 12 |
| `T2-012` | [acta](task_2/boards/T2-012.md) | expert_one | active_surveillance | active_surveillance | ✓ | 12 |
| `T2-013` | [acta](task_2/boards/T2-013.md) | expert_one | active_treatment | active_treatment | ✓ | 12 |
| `T2-014` | [acta](task_2/boards/T2-014.md) | expert_one | active_surveillance | active_surveillance | ✓ | 12 |
| `T2-015` | [acta](task_2/boards/T2-015.md) | expert_one | active_treatment | active_treatment | ✓ | 12 |
| `T2-016` | [acta](task_2/boards/T2-016.md) | expert_one | active_surveillance | active_surveillance | ✓ | 12 |
| `T2-017` | [acta](task_2/boards/T2-017.md) | expert_one | active_treatment | active_treatment | ✓ | 12 |
| `T2-019` | [acta](task_2/boards/T2-019.md) | expert_one | active_treatment | active_treatment | ✓ | 12 |
| `T2-020` | [acta](task_2/boards/T2-020.md) | expert_one | active_treatment | active_treatment | ✓ | 12 |
| `T2-021` | [acta](task_2/boards/T2-021.md) | expert_one | continued_surveillance | continued_surveillance | ✓ | 12 |
| `T2-022` | [acta](task_2/boards/T2-022.md) | expert_one | active_surveillance | active_surveillance | ✓ | 12 |
| `T2-023` | [acta](task_2/boards/T2-023.md) | expert_one | active_treatment | active_treatment | ✓ | 12 |
| `T2-024` | [acta](task_2/boards/T2-024.md) | expert_three | active_surveillance | active_surveillance | ✓ | 13 |
| `T2-025` | [acta](task_2/boards/T2-025.md) | expert_one | active_surveillance | active_surveillance | ✓ | 12 |
| `T2-026` | [acta](task_2/boards/T2-026.md) | expert_one | continued_surveillance | continued_surveillance | ✓ | 12 |
| `T2-027` | [acta](task_2/boards/T2-027.md) | expert_one | active_surveillance | active_surveillance | ✓ | 12 |
| `T2-028` | [acta](task_2/boards/T2-028.md) | expert_one | active_treatment | active_treatment | ✓ | 12 |
| `T2-029` | [acta](task_2/boards/T2-029.md) | expert_one | active_surveillance | active_surveillance | ✓ | 12 |
| `T2-030` | [acta](task_2/boards/T2-030.md) | expert_three | active_treatment | active_treatment | ✓ | 13 |
| `T2-033` | [acta](task_2/boards/T2-033.md) | expert_one | active_surveillance | active_surveillance | ✓ | 12 |
| `T2-034` | [acta](task_2/boards/T2-034.md) | expert_one | continued_surveillance | continued_surveillance | ✓ | 12 |
| `T2-035` | [acta](task_2/boards/T2-035.md) | expert_one | active_surveillance | active_surveillance | ✓ | 12 |
| `T2-036` | [acta](task_2/boards/T2-036.md) | expert_one | active_surveillance | active_surveillance | ✓ | 12 |
| `T2-037` | [acta](task_2/boards/T2-037.md) | expert_one | active_surveillance | active_surveillance | ✓ | 12 |
| `T2-038` | [acta](task_2/boards/T2-038.md) | expert_one | active_treatment | active_treatment | ✓ | 12 |
| `T2-039` | [acta](task_2/boards/T2-039.md) | expert_one | continued_surveillance | continued_surveillance | ✓ | 12 |
| `T2-040` | [acta](task_2/boards/T2-040.md) | expert_one | active_treatment | active_treatment | ✓ | 12 |
| `T2-041` | [acta](task_2/boards/T2-041.md) | expert_one | active_treatment | active_treatment | ✓ | 12 |
| `T2-042` | [acta](task_2/boards/T2-042.md) | expert_one | continued_surveillance | continued_surveillance | ✓ | 12 |
| `T2-044` | [acta](task_2/boards/T2-044.md) | expert_one | continued_surveillance | continued_surveillance | ✓ | 12 |
| `T2-045` | [acta](task_2/boards/T2-045.md) | expert_one | continued_surveillance | continued_surveillance | ✓ | 12 |
| `T2-046` | [acta](task_2/boards/T2-046.md) | expert_one | continued_surveillance | continued_surveillance | ✓ | 12 |
| `T2-047` | [acta](task_2/boards/T2-047.md) | expert_one | continued_surveillance | continued_surveillance | ✓ | 12 |
| `T2-048` | [acta](task_2/boards/T2-048.md) | expert_one | active_surveillance | active_surveillance | ✓ | 12 |
| `T2-049` | [acta](task_2/boards/T2-049.md) | expert_one | active_surveillance | active_surveillance | ✓ | 12 |
| `T2-050` | [acta](task_2/boards/T2-050.md) | expert_one | active_treatment | active_treatment | ✓ | 12 |
| `T2-052` | [acta](task_2/boards/T2-052.md) | expert_one | active_treatment | active_treatment | ✓ | 12 |
| `T2-053` | [acta](task_2/boards/T2-053.md) | expert_one | continued_surveillance | continued_surveillance | ✓ | 12 |
| `T2-054` | [acta](task_2/boards/T2-054.md) | expert_one | active_treatment | active_treatment | ✓ | 12 |
| `T2-055` | [acta](task_2/boards/T2-055.md) | expert_one | active_surveillance | active_surveillance | ✓ | 12 |
| `T2-056` | [acta](task_2/boards/T2-056.md) | expert_one | active_surveillance | active_surveillance | ✓ | 12 |
| `T2-057` | [acta](task_2/boards/T2-057.md) | expert_one | active_treatment | active_treatment | ✓ | 12 |
| `T2-058` | [acta](task_2/boards/T2-058.md) | expert_one | active_treatment | active_treatment | ✓ | 12 |
| `T2-059` | [acta](task_2/boards/T2-059.md) | expert_one | continued_surveillance | continued_surveillance | ✓ | 12 |
| `T2-060` | [acta](task_2/boards/T2-060.md) | expert_five | active_surveillance | active_surveillance | ✓ | 12 |
| `T2-061` | [acta](task_2/boards/T2-061.md) | expert_one | active_treatment | active_treatment | ✓ | 12 |
| `T2-101` | [acta](task_2/boards/T2-101.md) | expert_one | active_treatment | active_treatment | ✓ | 12 |
| `T2-102` | [acta](task_2/boards/T2-102.md) | expert_one | continued_surveillance | continued_surveillance | ✓ | 12 |
| `T2-103` | [acta](task_2/boards/T2-103.md) | expert_one | active_treatment | active_treatment | ✓ | 12 |
| `T2-104` | [acta](task_2/boards/T2-104.md) | expert_one | active_treatment | active_treatment | ✓ | 12 |
| `T2-105` | [acta](task_2/boards/T2-105.md) | expert_one | active_treatment | active_treatment | ✓ | 12 |
| `T2-106` | [acta](task_2/boards/T2-106.md) | expert_one | active_treatment | active_treatment | ✓ | 12 |
| `T2-107` | [acta](task_2/boards/T2-107.md) | expert_one | active_treatment | active_treatment | ✓ | 12 |
| `T2-109` | [acta](task_2/boards/T2-109.md) | expert_one | active_treatment | active_treatment | ✓ | 12 |
| `T2-110` | [acta](task_2/boards/T2-110.md) | expert_three | active_treatment | active_treatment | ✓ | 13 |
| `T2-111` | [acta](task_2/boards/T2-111.md) | expert_one | active_treatment | active_treatment | ✓ | 12 |

</details>

## Tarea 3 · pronóstico posoperatorio

75 actas. 0 decisiones contra la referencia, 5 con reapertura o respaldo.

### Reaperturas y respaldos (5)

| caso | acta | meses | event | respaldo | int. |
|---|---|---|---|---|---|
| `T3-019` | [acta](task_3/output/task3/T3-019/acta.md) | 84.8 | 0 | sí | 11 |
| `T3-022` | [acta](task_3/output/task3/T3-022/acta.md) | 62.8 | 0 | sí | 11 |
| `T3-060` | [acta](task_3/output/task3/T3-060/acta.md) | 62.8 | 1 | sí | 11 |
| `T3-068` | [acta](task_3/output/task3/T3-068/acta.md) | 69.4 | 0 | sí | 11 |
| `T3-072` | [acta](task_3/output/task3/T3-072/acta.md) | 76.7 | 0 | sí | 11 |

<details><summary>Los 70 restantes</summary>

| caso | acta | meses | event | respaldo | int. |
|---|---|---|---|---|---|
| `T3-001` | [acta](task_3/output/task3/T3-001/acta.md) | 31.2 | 1 |  | 11 |
| `T3-002` | [acta](task_3/output/task3/T3-002/acta.md) | 76.7 | 0 |  | 11 |
| `T3-003` | [acta](task_3/output/task3/T3-003/acta.md) | 76.7 | 0 |  | 11 |
| `T3-004` | [acta](task_3/output/task3/T3-004/acta.md) | 69.4 | 0 |  | 11 |
| `T3-005` | [acta](task_3/output/task3/T3-005/acta.md) | 62.8 | 0 |  | 11 |
| `T3-006` | [acta](task_3/output/task3/T3-006/acta.md) | 69.4 | 0 |  | 11 |
| `T3-007` | [acta](task_3/output/task3/T3-007/acta.md) | 84.8 | 0 |  | 11 |
| `T3-008` | [acta](task_3/output/task3/T3-008/acta.md) | 62.8 | 0 |  | 11 |
| `T3-009` | [acta](task_3/output/task3/T3-009/acta.md) | 56.8 | 0 |  | 11 |
| `T3-010` | [acta](task_3/output/task3/T3-010/acta.md) | 51.4 | 0 |  | 11 |
| `T3-011` | [acta](task_3/output/task3/T3-011/acta.md) | 69.4 | 0 |  | 11 |
| `T3-012` | [acta](task_3/output/task3/T3-012/acta.md) | 76.7 | 0 |  | 11 |
| `T3-013` | [acta](task_3/output/task3/T3-013/acta.md) | 62.8 | 0 |  | 11 |
| `T3-014` | [acta](task_3/output/task3/T3-014/acta.md) | 56.8 | 0 |  | 11 |
| `T3-015` | [acta](task_3/output/task3/T3-015/acta.md) | 62.8 | 0 |  | 11 |
| `T3-016` | [acta](task_3/output/task3/T3-016/acta.md) | 69.4 | 0 |  | 11 |
| `T3-017` | [acta](task_3/output/task3/T3-017/acta.md) | 42.1 | 1 |  | 11 |
| `T3-018` | [acta](task_3/output/task3/T3-018/acta.md) | 62.8 | 1 |  | 11 |
| `T3-020` | [acta](task_3/output/task3/T3-020/acta.md) | 51.4 | 0 |  | 11 |
| `T3-021` | [acta](task_3/output/task3/T3-021/acta.md) | 69.4 | 0 |  | 11 |
| `T3-023` | [acta](task_3/output/task3/T3-023/acta.md) | 84.8 | 1 |  | 11 |
| `T3-024` | [acta](task_3/output/task3/T3-024/acta.md) | 62.8 | 0 |  | 11 |
| `T3-025` | [acta](task_3/output/task3/T3-025/acta.md) | 38.1 | 1 |  | 11 |
| `T3-026` | [acta](task_3/output/task3/T3-026/acta.md) | 62.8 | 0 |  | 11 |
| `T3-027` | [acta](task_3/output/task3/T3-027/acta.md) | 56.8 | 1 |  | 11 |
| `T3-028` | [acta](task_3/output/task3/T3-028/acta.md) | 84.8 | 0 |  | 11 |
| `T3-029` | [acta](task_3/output/task3/T3-029/acta.md) | 69.4 | 0 |  | 11 |
| `T3-030` | [acta](task_3/output/task3/T3-030/acta.md) | 62.8 | 0 |  | 11 |
| `T3-031` | [acta](task_3/output/task3/T3-031/acta.md) | 51.4 | 0 |  | 11 |
| `T3-032` | [acta](task_3/output/task3/T3-032/acta.md) | 56.8 | 1 |  | 11 |
| `T3-033` | [acta](task_3/output/task3/T3-033/acta.md) | 34.5 | 1 |  | 11 |
| `T3-034` | [acta](task_3/output/task3/T3-034/acta.md) | 56.8 | 0 |  | 11 |
| `T3-035` | [acta](task_3/output/task3/T3-035/acta.md) | 84.8 | 0 |  | 11 |
| `T3-036` | [acta](task_3/output/task3/T3-036/acta.md) | 51.4 | 1 |  | 11 |
| `T3-037` | [acta](task_3/output/task3/T3-037/acta.md) | 62.8 | 0 |  | 11 |
| `T3-038` | [acta](task_3/output/task3/T3-038/acta.md) | 62.8 | 0 |  | 11 |
| `T3-039` | [acta](task_3/output/task3/T3-039/acta.md) | 51.4 | 1 |  | 11 |
| `T3-040` | [acta](task_3/output/task3/T3-040/acta.md) | 62.8 | 0 |  | 11 |
| `T3-041` | [acta](task_3/output/task3/T3-041/acta.md) | 76.7 | 0 |  | 11 |
| `T3-042` | [acta](task_3/output/task3/T3-042/acta.md) | 56.8 | 0 |  | 11 |
| `T3-043` | [acta](task_3/output/task3/T3-043/acta.md) | 62.8 | 0 |  | 11 |
| `T3-044` | [acta](task_3/output/task3/T3-044/acta.md) | 84.8 | 0 |  | 11 |
| `T3-045` | [acta](task_3/output/task3/T3-045/acta.md) | 62.8 | 0 |  | 11 |
| `T3-046` | [acta](task_3/output/task3/T3-046/acta.md) | 84.8 | 0 |  | 11 |
| `T3-047` | [acta](task_3/output/task3/T3-047/acta.md) | 42.1 | 1 |  | 11 |
| `T3-048` | [acta](task_3/output/task3/T3-048/acta.md) | 69.4 | 0 |  | 11 |
| `T3-049` | [acta](task_3/output/task3/T3-049/acta.md) | 84.8 | 0 |  | 11 |
| `T3-050` | [acta](task_3/output/task3/T3-050/acta.md) | 69.4 | 1 |  | 11 |
| `T3-051` | [acta](task_3/output/task3/T3-051/acta.md) | 69.4 | 0 |  | 11 |
| `T3-052` | [acta](task_3/output/task3/T3-052/acta.md) | 56.8 | 1 |  | 11 |
| `T3-053` | [acta](task_3/output/task3/T3-053/acta.md) | 69.4 | 1 |  | 11 |
| `T3-054` | [acta](task_3/output/task3/T3-054/acta.md) | 62.8 | 0 |  | 11 |
| `T3-055` | [acta](task_3/output/task3/T3-055/acta.md) | 51.4 | 0 |  | 11 |
| `T3-056` | [acta](task_3/output/task3/T3-056/acta.md) | 38.1 | 0 |  | 11 |
| `T3-057` | [acta](task_3/output/task3/T3-057/acta.md) | 69.4 | 1 |  | 11 |
| `T3-058` | [acta](task_3/output/task3/T3-058/acta.md) | 42.1 | 0 |  | 11 |
| `T3-059` | [acta](task_3/output/task3/T3-059/acta.md) | 69.4 | 1 |  | 11 |
| `T3-061` | [acta](task_3/output/task3/T3-061/acta.md) | 62.8 | 0 |  | 11 |
| `T3-062` | [acta](task_3/output/task3/T3-062/acta.md) | 38.1 | 0 |  | 11 |
| `T3-063` | [acta](task_3/output/task3/T3-063/acta.md) | 42.1 | 0 |  | 11 |
| `T3-064` | [acta](task_3/output/task3/T3-064/acta.md) | 42.1 | 0 |  | 11 |
| `T3-065` | [acta](task_3/output/task3/T3-065/acta.md) | 69.4 | 0 |  | 11 |
| `T3-066` | [acta](task_3/output/task3/T3-066/acta.md) | 62.8 | 0 |  | 11 |
| `T3-067` | [acta](task_3/output/task3/T3-067/acta.md) | 69.4 | 0 |  | 11 |
| `T3-069` | [acta](task_3/output/task3/T3-069/acta.md) | 62.8 | 0 |  | 11 |
| `T3-070` | [acta](task_3/output/task3/T3-070/acta.md) | 28.2 | 1 |  | 11 |
| `T3-071` | [acta](task_3/output/task3/T3-071/acta.md) | 34.5 | 1 |  | 11 |
| `T3-073` | [acta](task_3/output/task3/T3-073/acta.md) | 56.8 | 0 |  | 11 |
| `T3-074` | [acta](task_3/output/task3/T3-074/acta.md) | 84.8 | 0 |  | 11 |
| `T3-075` | [acta](task_3/output/task3/T3-075/acta.md) | 93.7 | 0 |  | 11 |

</details>


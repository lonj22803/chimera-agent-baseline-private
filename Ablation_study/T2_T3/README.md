# Ablacion T2/T3

Extension ejecutable del estudio T1 para reducir las arquitecturas de decision de tratamiento
(T2) y pronostico de recurrencia (T3), sin editar la V4.

- `PLAN_ABLACION_T2_T3.md`: fases, compuertas y estado.
- `PREREGISTRO.md`: hipotesis, margenes y brazos congelados.
- `harness/`: simuladores, variantes reversibles, runners, juez y sintesis.
- `results/`: resultados estructurados y estado del guardian.
- `reports/INFORME_ABLACION_T2_T3.md`: informe final.
- `runs/`: salidas regenerables, ignoradas por Git.

Entrada autonoma: `Ablation_study/T2_T3/harness/guardian.sh`.

## Ejecucion autonoma

El guardian reanuda casos y evaluaciones ya completos. Desde la raiz del repositorio:

```bash
tmux new-session -d -s ablation-t23 \
  'bash Ablation_study/T2_T3/harness/guardian.sh'
```

Estado y seguimiento:

```bash
cat Ablation_study/T2_T3/results/guardian_status.json
tail -f Ablation_study/T2_T3/logs/guardian.log
tmux attach -t ablation-t23
```

Desconectarse sin detenerlo: `Ctrl-b`, luego `d`. La sesion termina sola cuando
`cierre.json` es valido y el informe queda escrito.

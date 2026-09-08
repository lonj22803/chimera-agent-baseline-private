# Informe de la corrida `all` sobre los casos sin etiqueta

195 casos en la corrida: 91 etiquetados, **104 sin etiqueta**.

## 1. Integridad

- casos entregados: 104/104 (100%); fallos: 0
- respaldo determinista del presidente: 2/104 (2%) — ['f13bd8', '70b8e6']
- precedente idéntico (debe ser 0): 0
- tiempo por caso: media 29.9 s, máximo 43.3 s
- reaperturas del verificador: 0

## 2. Qué decidió y por qué regla

- decisión: yes 75/104 (72%), no 29/104 (28%) — en la serie etiquetada el urólogo: yes 56/91 (62%)
- por cubo (sin etiqueta → serie etiquetada):
  - `None`: n=25, yes 20/25 (80%) → urólogo yes 20/24 (83%) sobre 24
  - `Negative`: n=12, yes 7/12 (58%) → urólogo yes 13/18 (72%) sobre 18
  - `Positive`: n=67, yes 48/67 (72%) → urólogo yes 23/49 (47%) sobre 49
- peldaño del protocolo que decidió:
  - cohort criterion: 47
  - weighted vote of the trained experts: 43
  - documented prior grade: 14
- grado documentado leído en el cubo positivo: 18/67 (27%) — reparto {'None': 49, '1': 7, '2': 7, '3': 4}

## 3. La traza que se entrega

- confianza: clear 104/104 (100%) — urólogo: clear 58/91 (64%), borderline 18/91 (20%), uncertain 15/91 (16%)
- secciones abiertas (frecuencia sin etiqueta → urólogo en la serie):
  - radiology_report: 104/104 (100%) → 88/91 (97%)
  - psa_trend: 104/104 (100%) → 79/91 (87%)
  - previous_notes: 104/104 (100%) → 77/91 (85%)
  - laboratory_results: 46/104 (44%) → 41/91 (45%)
  - family_history: 0/104 (0%) → 0/91 (0%)
- casos en que lo abierto difiere del plan: 0
- casos con plan vacío (el urólogo no abriría nada): 0
- pesos entregados (moda y frecuencia): bx=important 68%, fh=not_used 100%, age=important 100%, dre=not_used 56%, psa=important 100%, vol=noted 100%, psad=noted 100%, cspca=not_used 100%, pirads=important 63%, comorbidity=noted 100%

## 4. La sala

- grounding guard:dre, fh -> not_used: 58
- grounding guard:fh -> not_used: 46
- chair:challenged: 32
- chair:decision settled by PANEL-PROTOCOL after t: 27
- chair confidence 'borderline' logged; trace conf: 18
- registrar:unsourced values challenged: 16
- registrar:still unsourced after challenge: 5
- chair attempt 1:OutputParserException: 3
- chair attempt 2:OutputParserException: 2
- chair attempt 3:OutputParserException: 2
- chair:deterministic fallback used: 2
- chair confidence 'uncertain' logged; trace confi: 1
- chair directive failed:OutputParserException: 1
- el presidente disintió del protocolo en 32/104 (31%); se entregó el protocolo en todos
- preguntas abiertas por caso: media 2.0
- EXPERT-IMAGE convocado: 0
- longitud del free_text: media 431 caracteres, mínimo 333
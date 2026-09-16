"""La orquestación de la fase 7: que traduzca banderas y que no ablande el criterio."""
from __future__ import annotations
import json
from pathlib import Path
import pytest

from version_final_reto.tasks_complete import contrato, experimento, runner

V1 = Path(__file__).resolve().parents[2]


def test_runner_traduce_las_banderas_de_cada_tarea():
    uno = runner.build_command(1, '/tmp/o', 'all')
    assert uno[-4:] == ['--out-root', '/tmp/o', '--split', 'all']
    assert '--backend' not in uno, 'T1 no tiene backend seleccionable'
    tres = runner.build_command(3, '/tmp/o', 'all', backend='vllm')
    assert tres[tres.index('--backend')+1] == 'vllm'
    assert tres[tres.index('--mode')+1] == 'deployed', 'vLLM implica expertos desplegados'
    assert runner.build_command(3, '/tmp/o', 'all', backend='ollama')[-1] == 'oof'


def test_los_ficheros_escritos_son_los_que_declara_grand_challenge():
    """Confirmado contra la página del algoritmo: canonical, y sin alias de más."""
    check = contrato.check_slugs()
    assert check['passed'] and not check['desajuste'], check['desajuste']
    for task, names in check['filenames'].items():
        assert len(names) == 2, f'La tarea {task} escribe exactamente dos ficheros'
    assert check['user_confirmation'] is True


def test_el_alias_escribiria_un_fichero_de_mas():
    """Por qué canonical es el defecto: GC no declara `-reas`, y un extra también falla."""
    from version_final_reto.common.slugs import output_filenames
    assert len(output_filenames(3, '')) == 3
    assert sorted(output_filenames(3, 'canonical')) == sorted(contrato.GC_OUTPUTS[3])


def test_la_cobertura_exige_los_423_casos(tmp_path):
    for task in (1, 2, 3):
        (tmp_path/f'task{task}').mkdir()
    result = contrato.check_coverage(tmp_path)
    assert not result['passed'] and not result['complete']
    assert result['expected_total'] == 423 and result['valid_total'] == 0


def test_formularios_detecta_claves_incompletas(tmp_path):
    """La causa raíz que tumbó la entrega anterior: 8 claves donde el contrato pide 11."""
    case = tmp_path/'task2'/'T2-001'
    case.mkdir(parents=True)
    (tmp_path/'task1').mkdir()
    (case/'prostate-treatment-decision-reasoning.json').write_text(json.dumps(
        {'variable_weights': {'age': 'not_used', 'psa': 'important'}}))
    result = contrato.check_forms(tmp_path)
    assert not result['passed']
    fallo = next(o for o in result['offenders'] if o.get('case_id') == 'T2-001')
    assert 'bx_isup' in fallo['missing']


def test_la_compuerta_no_pasa_sin_corrida_completa():
    assert contrato.gate(output_root=None)['passed'] is False


@pytest.mark.parametrize('dev_b,dev_c,val_b,val_c,esperado,motivo', [
    (0.70, 0.65, None, None, False, 'No mejora en DEV; VAL no se lee'),
    (0.70, 0.80, None, None, False, 'Elegible en DEV; falta confirmar en VAL'),
    (0.7623, 0.8010, 0.7566, 0.7297, False, experimento.RECHAZOS['val']),
    (0.7623, 0.8010, 0.7566, 0.7700, True, None),
])
def test_criterio_de_adopcion(dev_b, dev_c, val_b, val_c, esperado, motivo):
    veredicto = experimento.decidir(dev_b, dev_c, val_b, val_c)
    assert veredicto['adoptado'] is esperado and veredicto['motivo'] == motivo


def test_no_mejorar_en_dev_impide_leer_val():
    """VAL sólo confirma. Leerlo cuando DEV no mejora lo convierte en un segundo DEV."""
    assert experimento.decidir(0.70, 0.65, 0.60, 0.99)['val_leido'] is False


def test_los_splits_fijos_no_se_resortean():
    dev, val = experimento.split_ids(3, 'dev'), experimento.split_ids(3, 'val')
    assert len(dev) == 52 and len(val) == 23
    assert not set(dev) & set(val), 'DEV y VAL no pueden compartir casos'


def test_el_resumen_conserva_el_veredicto_de_cada_experimento():
    filas = {f['experimento']: f for f in experimento.resumen_resultados()}
    assert filas['forms']['adoptado'] is False, 'El candidato de formularios se rechazó en DEV'
    assert filas['survival_total']['elegible'] is True, 'La supervivencia quedó elegible, sin adoptar'

import pytest
from version_final_reto.common import guards,prompt_kit
from version_final_reto.task_2.experts_2.experience import ProfessionalExperience
from version_final_reto.task_3.experts_3.experience import ProfessionalExperience as T3Experience
from version_final_reto.common.chimera_experts.io import Case


def test_grade_abbreviations_without_deriving_grade_from_gleason():
    assert not guards.unsourced_grades('ISUP 2; Gleason 3+4', 'ISUP Grade Group 2; Gleason score 3+4')
    assert guards.unsourced_grades('ISUP 3', 'ISUP Grade Group 2') == ['ISUP 3']
    assert guards.unsourced_grades('ISUP 2', 'Gleason 3+4') == ['ISUP 2']
    assert guards.unsourced_grades('Gleason 4+3', 'Gleason 3+4') == ['Gleason 4+3']


def test_t2_cannot_retrieve_itself_or_vote():
    row={'case_id':'same','bucket':'1','features':[0]*10,'variable_weights':{},'confidence':'clear'}
    expert=ProfessionalExperience(rows=[row])
    result=expert.recall('same',{'bx_isup':1})
    assert not result['available'] and result['neighbours']==[]
    assert 'decision' not in result
    with pytest.raises(ValueError,match='excludes'):
        ProfessionalExperience(rows=[row],exclude_self=False)


def test_t3_outcome_is_never_a_prediction(tmp_path):
    import json
    path=tmp_path/'memory.json'
    path.write_text(json.dumps({'rows':[{'case_id':'self','score':3,'group':'intermediate','months':9,'event':1}]}))
    result=T3Experience(path).recall(Case('self',3),3)
    assert result['neighbours']==[]
    assert not {'months_to_recurrence','risk','event','decision'} & result.keys()


def test_all_llm_system_roles_have_trust_boundary():
    from version_final_reto.task_1.agent import prompts as p1
    from version_final_reto.task_2.agent import prompts as p2
    from version_final_reto.task_3.agent import prompts as p3
    for module in (p1,p2):
        for role in ('EAU','MODERATOR','REGISTRAR','VERIFIER','CHAIR'):
            assert prompt_kit.ANTI_INJECTION in getattr(module,role+'_SYSTEM')
    assert prompt_kit.ANTI_INJECTION in p3.CHAIR


def test_selected_horizon_replays_nested_order_and_has_no_current_labels():
    import json
    import numpy as np
    from pathlib import Path
    from version_final_reto.task_3.agent.protocol import Panel, EXPERTS
    from version_final_reto.task_3.experts_3.train.protocol import concordance
    from version_final_reto.common.chimera_experts.io import load_cases
    data=json.loads((EXPERTS/'train/artifacts/spokesperson_candidate.json').read_text())
    panel=Panel('oof',spokesperson='selected')
    cases=load_cases(Path(__file__).resolve().parents[3]/'data/task3',3,labelled_only=True)
    from version_final_reto.common.chimera_experts import dataset_task3 as ds
    times=np.array([c.label['months_to_recurrence'] for c in cases]);events=np.array([c.label['event'] for c in cases])
    predictions=[]
    for c in cases:
        c.label=None; c.reasoning=None
        predictions.append(panel.horizon(c,ds._surgical(c)['capra_s'])['months_to_recurrence'])
    assert concordance(times,np.array(predictions),events)==data['evaluation']['candidate_c_index']

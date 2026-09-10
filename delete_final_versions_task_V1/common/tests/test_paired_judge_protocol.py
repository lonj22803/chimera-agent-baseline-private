import json
from types import SimpleNamespace
import pytest
from delete_final_versions_task_V1.experiments import paired_judge as paired


def prepare(tmp_path,monkeypatch,scores):
    from dev import score_with_judge as loader
    (tmp_path/'dev/splits').mkdir(parents=True)
    (tmp_path/'dev/splits/task2_dev.txt').write_text('patient\n')
    (tmp_path/'evaluation').mkdir();(tmp_path/'evaluation/evaluate.py').write_text('# fixture evaluator\n')
    counts={'build':0,'calls':[]}
    def build():counts['build']+=1;return object()
    def evaluate(gt,pred,tool,judge):
        counts['calls'].append(pred['variant'])
        value=scores[len(counts['calls'])-1]
        return {'case_id':'patient','decision_score':1.,'rationale_score':value}
    ev=SimpleNamespace(build_rationale_judge=build,get_case_id=lambda r:r['case_id'],
                       load_ground_truth_records=lambda *a:[{'case_id':'patient'}],
                       evaluate_case=evaluate,compute_aggregate_metrics=lambda r:{'ranking_score':r[0]['rationale_score']})
    monkeypatch.setattr(paired,'ROOT',tmp_path)
    monkeypatch.setattr(paired,'api',lambda *a:{'models':[{'name':'fake'}]})
    monkeypatch.setattr(paired,'runners',lambda:['1234'])
    monkeypatch.setattr(loader,'DEFAULT_EVAL_REPO',tmp_path)
    monkeypatch.setattr(loader,'load_evaluator',lambda *a:ev)
    monkeypatch.setattr(loader,'load_predictions',lambda p,*a:{'patient':{'variant':p.name}})
    return counts


def test_two_passes_one_judge_and_no_adoption_from_one_good_pass(tmp_path,monkeypatch):
    counts=prepare(tmp_path,monkeypatch,[.5,.8,.4,.6])
    result=paired.run(tmp_path/'baseline',tmp_path/'candidate',2,'dev',tmp_path/'result.json')
    assert counts=={'build':1,'calls':['baseline','candidate','candidate','baseline']}
    assert not result['eligible']
    assert len(result['passes'])==2


def test_changed_residency_invalidates_pair(tmp_path,monkeypatch):
    prepare(tmp_path,monkeypatch,[.5,.8,.8,.5])
    calls=iter([['1234'],['9999']])
    monkeypatch.setattr(paired,'runners',lambda:next(calls))
    with pytest.raises(RuntimeError,match='runner changed'):
        paired.run(tmp_path/'baseline',tmp_path/'candidate',2,'dev',tmp_path/'result.json')
    assert not (tmp_path/'result.json').exists()

"""Deterministic evidence inventory; RAG is optional and has no numerical authority.

The existing G block describes pre-treatment clinical risk, not a validated
postoperative EAU/NCCN group. Missing cT must remain unknown. Postoperative
adverse findings are declared separately rather than relabelling that group.
"""
import math
from version_final_reto.common.chimera_experts import dataset_task3 as ds


def assess(case, findings):
    grading = ds._grading(case)
    group = next((name for name in ('low', 'intermediate', 'high') if grading.get('eau_'+name) == 1), None)
    return {'authority': 'advisory; no vote or numeric horizon',
            'clinical_eau_group_from_G': group or 'not recorded',
            'scope': 'G is pre-treatment clinical stratification; not a postoperative EAU/NCCN classification.',
            'postoperative_findings': {k: findings.get(k) if isinstance(findings.get(k), (int, float))
                                      and math.isfinite(findings[k]) else None
                                      for k in ('epe', 'margins', 'svi', 'lvi', 'ln_unknown')},
            'follow_up': 'Postoperative PSA and its trajectory are needed; pathology alone does not establish biochemical recurrence.',
            'reference': 'EAU Prostate Cancer: Follow-up, https://uroweb.org/guidelines/prostate-cancer/chapter/followup',
            'retrieval': 'deterministic inventory; no guideline passage was retrieved'}


async def retrieve(tools, case_id):
    # The upstream registry already defines TASK3_TOOLS, including search_guidelines.
    from chimera_agent_baseline.tools.definitions import TASK3_TOOLS
    tool = next((t for t in tools if t.name == 'search_guidelines'), None)
    if tool is None:
        raise ValueError('T3 RAG enabled but search_guidelines is unavailable')
    result = await tool.ainvoke({'query': 'prostate cancer radical prostatectomy postoperative PSA follow-up adverse pathology'})
    return {'retrieved': result, 'authority': 'guideline evidence only; no treatment vote or numeric horizon',
            'registry': 'TASK3_TOOLS', 'case_id': case_id}

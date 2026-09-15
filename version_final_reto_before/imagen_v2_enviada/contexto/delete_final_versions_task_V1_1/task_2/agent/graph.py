"""Junta LangGraph de tarea 2, con acta global y lectura MCP restringida al plan."""
from __future__ import annotations

import asyncio
import json
import operator
import os
from delete_final_versions_task_V1_1.common import prompt_kit
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph

from delete_final_versions_task_V1_1.common import deadline, guards, sampling
from delete_final_versions_task_V1_1.common.board import Board
from . import decide, prompts, protocol as P


class BoardState(TypedDict, total=False):
    case_id: str
    task: int
    prompt_payload: dict
    case_files: dict
    case_prompt: str
    interventions: Annotated[list[dict], operator.add]
    warnings: Annotated[list[str], operator.add]
    experience: dict
    experts: dict
    planned: list[str]
    documents: dict
    revealed: list[str]
    tools_called: list[str]
    questions: list[str]
    document_questions: dict
    protocol: dict
    verdict: dict
    structured_response: dict
    chair_audit: dict
    pass_: int


def _say(state, speaker, body, data=None):
    return {'n': len(state.get('interventions', [])) + 1, 'speaker': speaker,
            'body': body, 'data': data or {}, 'pass_': state.get('pass_', 1)}


def _mcp_payload(value):
    """Normaliza la respuesta de ``tool.ainvoke()`` a un dict.

    langchain_mcp_adapters devuelve, segun la version/transporte, una de tres
    formas: una cadena JSON, un dict ya parseado, o (el caso real observado
    aqui) una LISTA de bloques de contenido MCP:
    ``[{'type': 'text', 'text': '<json>'}]``. El codigo anterior solo
    contemplaba cadena o dict, asi que la lista caia siempre al ``else`` y
    NINGUN documento se abria jamas -- 12 avisos por caso, en los 5 casos que
    llegaron a correr antes de pararlo. Bug encontrado el 2026-09-09 al
    verificar la corrida completa, no la prueba de un solo caso.
    """
    if isinstance(value, list):
        text = ''.join(b.get('text', '') for b in value
                       if isinstance(b, dict) and b.get('type') == 'text')
        return guards.parse_json(text)
    if isinstance(value, str):
        return guards.parse_json(value)
    return value if isinstance(value, dict) else {}


def _render(state):
    return Board.from_dicts(state['case_id'], 2, state.get('interventions', [])).render()


def create_conference_graph(tools, model, panel=None, *, max_passes=2,
                            chair_max_retries=3, step_timeout=900,
                            temperature=0.0, token_scale=1.0):
    experience = None
    if os.environ.get('CHIMERA_T2_EXPERIENCE') == '1' or os.environ.get('CHIMERA_T2_FORM') == 'experience':
        from ..experts_2.experience import ProfessionalExperience
        experience = ProfessionalExperience()
    reader = panel if panel is not None else P.ExpertReader()
    by_name = {tool.name: tool for tool in tools}
    section_tools = {section: by_name[name] for name, section in P.SECTION_BY_TOOL.items()
                     if name in by_name}
    voices = {role: sampling.speak_as(model, voice) for role, voice in
              sampling.voices(temperature, token_scale).items()}

    async def speak(role, system, user, allowed=(), budget=0, required=()):
        """Bounded tool session: reject outside-plan calls and never repeat a tool."""
        messages = [SystemMessage(content=system), HumanMessage(content=user)]
        results, errors, used = {}, [], set()
        allowed = {t.name: t for t in allowed}
        base = voices[role]
        bound = base.bind_tools(list(allowed.values())) if allowed else base
        async def call(name, args):
            # The current patient is selected in code, not by generated arguments.
            try:
                raw = await allowed[name].ainvoke(args)
                payload = _mcp_payload(raw)
                results[name] = payload
                return (json.dumps(payload, ensure_ascii=False) if payload
                        else 'Retrieval failed; no evidence obtained.')
            except Exception as exc:
                errors.append(f'{role}/{name}: {type(exc).__name__}: {exc}')
                results[name] = {}
                return 'Retrieval failed; no evidence obtained.'
        for _ in range(budget + 2):
            try:
                response = await bound.ainvoke(messages)
            except Exception as exc:
                errors.append(f'{role}: {type(exc).__name__}: {exc}')
                break
            messages.append(response)
            calls = getattr(response, 'tool_calls', [])
            if not calls:
                break
            for tc in calls:
                name = tc['name']
                if name not in allowed or name in used or len(used) >= budget:
                    content = 'Rejected: tool outside plan, already called, or budget exhausted.'
                else:
                    used.add(name)
                    args = dict(tc.get('args') or {})
                    if name in P.SECTION_BY_TOOL:
                        args = {'case_id': active_case.get()}
                    content = await call(name, args)
                messages.append(ToolMessage(content=content, name=name, tool_call_id=tc['id']))
        # The registrar must open the exact plan even if the LLM omits a call.
        for name in required:
            if name not in used and name in allowed and len(used) < budget:
                used.add(name)
                content = await call(name, {'case_id': active_case.get()})
                call_id = f'required-{name}'
                messages += [AIMessage(content='', tool_calls=[dict(name=name,
                    args={'case_id': active_case.get()}, id=call_id, type='tool_call')]),
                    ToolMessage(content=content, name=name, tool_call_id=call_id)]
        # A mandatory RAG retrieval is also enforced if the model wrote without searching.
        if role == 'eau' and 'search_guidelines' in allowed and not used:
            used.add('search_guidelines')
            content = await call('search_guidelines', {'query': 'prostate cancer management after biopsy active surveillance treatment'})
            messages += [AIMessage(content='', tool_calls=[dict(name='search_guidelines',
                args={'query': 'prostate cancer management after biopsy active surveillance treatment'},
                id='required-guideline', type='tool_call')]),
                ToolMessage(content=content, name='search_guidelines', tool_call_id='required-guideline')]
        if messages and isinstance(messages[-1], ToolMessage):
            try:
                messages.append(await base.ainvoke(messages + [HumanMessage(content=prompt_kit.FINALIZE)]))
            except Exception as exc:
                errors.append(f'{role}/finalize: {type(exc).__name__}: {exc}')
        text = next((m.content for m in reversed(messages) if isinstance(m, AIMessage)
                     and m.content and not m.tool_calls), '')
        return str(text), results, errors

    # ContextVar keeps simultaneous ainvoke calls isolated.
    from contextvars import ContextVar
    active_case = ContextVar('task2_current_case')

    async def reading(state, name, documents=None):
        clinical = documents or {}
        # Embeddings are available only for modalities whose reports were retrieved.
        features = {k: v for k, v in state.get('case_files', {}).get('features', {}).items()
                    if ('radiology_report' in clinical and 'mri' in k.lower()) or
                       ('pathology_report' in clinical and 'biopsy' in k.lower())}
        try:
            return await asyncio.to_thread(reader.predict, name, state['case_id'],
                state['prompt_payload'], clinical, features)
        except Exception as exc:
            return {'available': False, 'error': f'{type(exc).__name__}: {exc}'}

    def intake(state):
        return {'interventions': [_say(state, 'INTAKE', json.dumps(state['prompt_payload'],
                ensure_ascii=False, indent=2))], 'pass_': 1, 'documents': {}, 'revealed': []}

    async def grade(state):
        result = await reading(state, 'expert_one')
        return {'experts': {'expert_one': result}, 'interventions': [
            _say(state, 'EXPERT-GRADE', P.render_expert('expert_one', result), result)]}

    def pathology(state):
        result = {'available': False, 'pending': 'pathology_report', 'replica_of': 'expert_one'}
        return {'interventions': [_say(state, 'EXPERT-PATHOLOGY',
            'Second reading and upgrade assessment pending pathology retrieval. Confirmatory replica, not a vote.', result)]}

    async def cascade(state):
        result = await reading(state, 'expert_five')
        return {'experts': {**state['experts'], 'expert_five': result}, 'interventions': [
            _say(state, 'EXPERT-CASCADE', P.render_expert('expert_five', result), result)]}

    def trace(state):
        data = P.trace(state['prompt_payload'])
        # Missing tools remain on the plan so the verifier can report them.
        return {'planned': data['internal_plan'], 'interventions': [_say(state, 'EXPERT-TRACE',
            'reasoning_task2 form baseline: moda, confidence clear, delivered reveal_sequence []. '
            'Internal reading plan is fixed by model source requirements, not the rejected learned reveal policy.\n'
            + json.dumps(data), data)]}

    async def eau(state):
        active_case.set(state['case_id'])
        text, results, errors = await speak('eau', prompts.EAU_SYSTEM, _render(state),
            [by_name['search_guidelines']] if 'search_guidelines' in by_name else [], budget=2)
        if not results:
            text = 'No guideline passage retrieved; no guideline claim is supported.'
        return {'interventions': [_say(state, 'EXPERT-EAU', text, {'retrievals': results})], 'warnings': errors}

    async def moderator(state):
        text, _, errors = await speak('moderator', prompts.MODERATOR_SYSTEM,
            _render(state) + '\nFixed plan: ' + json.dumps(state['planned']))
        obj = guards.parse_json(text)
        questions = obj.get('document_questions', {})
        if not isinstance(questions, dict):
            questions = {}
        questions = {s: str(questions.get(s) or f'What additional findings in {s} affect management?')
                     for s in state['planned']}
        general = obj.get('questions', [])
        general = [str(q) for q in general][:4] if isinstance(general, list) else []
        return {'document_questions': questions, 'questions': general, 'warnings': errors,
            'interventions': [_say(state, 'MODERATOR', json.dumps(questions), {'questions': general})]}

    async def registrar(state):
        active_case.set(state['case_id'])
        pending = [s for s in state['planned'] if s not in state['documents']]
        allowed = [section_tools[s] for s in pending if s in section_tools]
        text, results, errors = await speak('registrar', prompts.REGISTRAR_SYSTEM,
            _render(state) + '\nOpen exactly: ' + json.dumps({s: state['document_questions'][s] for s in pending}),
            allowed, budget=len(allowed), required=[t.name for t in allowed])
        documents = dict(state['documents'])
        for name, value in results.items():
            section = P.SECTION_BY_TOOL[name]
            # `value` ya llega normalizado a dict desde call()/_mcp_payload().
            # Empty/malformed or explicit tool failures are not successful reveals.
            if isinstance(value, dict) and section in value and value[section] is not None:
                documents[section] = value[section]
            else:
                errors.append(f'{name}: response did not contain {section}')
        source = decide.clinical_sources(state['prompt_payload'], documents)
        offenders = guards.unsourced_values(text, source, '') + guards.unsourced_grades(text, source)
        if offenders:
            replacement, _, challenge_errors = await speak('registrar', prompts.REGISTRAR_SYSTEM,
                source + '\n' + prompts.registrar_quote_challenge(offenders))
            errors.extend(challenge_errors)
            text = replacement
        text = '\n'.join(line for line in text.splitlines()
                         if not guards.unsourced_values(line, source, '')
                         and not guards.unsourced_grades(line, source))
        return {'documents': documents, 'revealed': list(documents),
            'tools_called': [name for name, section in P.SECTION_BY_TOOL.items() if section in documents],
            'warnings': errors, 'interventions': [_say(state, 'REGISTRAR', text or 'No readable report.',
                                                      {'opened': list(documents), 'tool_results': results})]}

    async def fusion(state):
        docs = state['documents']
        experts = dict(state['experts'])
        if 'pathology_report' in docs:
            experts['expert_two'] = await reading(state, 'expert_two', docs)
        else:
            experts['expert_two'] = {'available': False, 'pending': 'pathology_report'}
        experts['expert_four'] = await reading(state, 'expert_four', docs)
        # Update the cascade after actual retrieval, keeping the opening bid in the acta.
        experts['expert_five'] = await reading(state, 'expert_five', docs)
        body = P.render_expert('expert_four', experts['expert_four'])
        body += '\nPathology follow-up: ' + P.render_expert('expert_two', experts['expert_two'])
        body += '\nCascade with retrieved sources: ' + P.render_expert('expert_five', experts['expert_five'])
        return {'experts': experts, 'interventions': [_say(state, 'EXPERT-FUSION', body, experts)]}

    async def fitness(state):
        result = await reading(state, 'expert_three', state['documents'])
        return {'experts': {**state['experts'], 'expert_three': result}, 'interventions': [
            _say(state, 'EXPERT-FITNESS', P.render_expert('expert_three', result), result)]}

    def experience_turn(state):
        from ..experts_2.experience import render
        result = experience.recall(state['case_id'], state['prompt_payload'])
        return {'experience': result, 'interventions': [_say(state, 'EXPERT-EXPERIENCE', render(result), result)]}

    def protocol(state):
        result = P.consolidate(state['prompt_payload'], state['experts'], state['revealed'])
        recalled = state.get('experience', {})
        if os.environ.get('CHIMERA_T2_FORM') == 'experience' and recalled.get('available'):
            result['variable_weights'] = recalled['variable_weights']
            result['confidence'] = recalled['confidence']
            result['policy'] = 'experimental_experience_form'
        return {'protocol': result, 'interventions': [_say(state, 'PANEL-PROTOCOL', json.dumps(result), result)]}

    async def verifier(state):
        active_case.set(state['case_id'])
        missing = [s for s in state['planned'] if s not in state['documents']]
        text, _, errors = await speak('verifier', prompts.VERIFIER_SYSTEM,
            _render(state) + '\nMissing planned documents: ' + json.dumps(missing),
            [by_name['search_guidelines']] if 'search_guidelines' in by_name else [], budget=1)
        # La segunda vuelta son cuatro llamadas más; si el reloj del caso no da,
        # se cierra con lo que hay: la cascada de guía ya decidió y el presidente
        # sólo tiene que redactar.
        reopen = bool(missing and 'VERDICT: not-ready' in text and state['pass_'] < max_passes
                      and deadline.allows('pass'))
        verdict = {'ready': not missing, 'missing': missing, 'reopened': reopen}
        return {'verdict': verdict, 'pass_': state['pass_'] + int(reopen), 'warnings': errors,
            'interventions': [_say(state, 'VERIFIER', text + '\nActual missing: ' + json.dumps(missing), verdict)]}

    async def chair(state):
        digest = prompts.clinical_digest(state['prompt_payload'], state['documents'], state['protocol']['decision'])
        if prompt_kit.enhanced(2):
            digest += prompt_kit.chair_context(2, state['prompt_payload'], state['case_id'])
        note, errors, attempts = None, [], 0
        for attempts in range(1, chair_max_retries + 1):
            text, _, faults = await speak('chair', prompts.CHAIR_SYSTEM, digest + (
                '\nPrevious attempt invalid: ' + '; '.join(errors[-4:]) if errors else ''))
            errors.extend(faults)
            candidate = guards.parse_json(text).get('reasoning')
            if not isinstance(candidate, str) or len(candidate.strip()) < 40:
                errors.append('chair: missing or too short reasoning JSON')
                continue
            faults = decide.note_faults(candidate, state['prompt_payload'], state['documents'])
            if faults:
                errors.append('chair: unsupported/process prose: ' + ', '.join(faults))
                continue
            note = candidate
            break
        out, downgraded = decide.build_output(state['case_id'], state['prompt_payload'],
            state['protocol'], state['revealed'], note)
        audit = {'schema_ok': True, 'attempts': attempts, 'fallback_note': note is None,
                 'fallback_form': note is None, 'grounding_downgraded': downgraded,
                 'note_violations': decide.note_faults(out['reasoning'], state['prompt_payload'], state['documents'])}
        return {'structured_response': out, 'chair_audit': audit, 'warnings': errors,
                'interventions': [_say(state, 'CHAIR', out['reasoning'], {**out, 'audit': audit})]}

    graph = StateGraph(BoardState)
    sequence = [('intake', intake), ('grade', grade), ('pathology', pathology), ('cascade', cascade),
                ('trace', trace), ('eau', eau), ('moderator', moderator), ('registrar', registrar), ('fusion', fusion)]
    if experience is not None:
        sequence.insert(4, ('experience', experience_turn))
    for name, fn in sequence + [('fitness', fitness), ('protocol', protocol), ('verifier', verifier), ('chair', chair)]:
        graph.add_node(name, fn)
    previous = START
    for name, _ in sequence:
        graph.add_edge(previous, name)
        previous = name
    graph.add_conditional_edges('fusion', lambda s: 'fitness' if P.fitness_needed(s['experts']) else 'protocol',
                                {'fitness': 'fitness', 'protocol': 'protocol'})
    graph.add_edge('fitness', 'protocol')
    graph.add_edge('protocol', 'verifier')
    graph.add_conditional_edges('verifier', lambda s: 'moderator' if s['verdict']['reopened'] else 'chair',
                                {'moderator': 'moderator', 'chair': 'chair'})
    graph.add_edge('chair', END)
    compiled = graph.compile()
    compiled.step_timeout = step_timeout
    return compiled

# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : model_probe_inspect.py
# Description : Consultation hors ligne des preuves de recette du planificateur
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Inspect probe documents without opening a mission store or replaying a call.

Checks cover document consistency, not model provenance or SQLite evidence.
Only the fixed suite's known filenames are read, never paths from a document.
Run this after the writer has stopped; this is not a cross-file atomic snapshot.
"""
from datetime import datetime
import os
from pathlib import Path
import re
import stat

from .contracts import digest
from .model_probe import CALL_BUDGET, CRITERIA, INCOMPLETE, SCHEMA, SUITE, corpus
from .presentation import header, message
from .qualification import ReportError, load
from .qualification_io import QualificationCheckError, read_report
from .tools import Policy, default_registry

INSPECTION_SCHEMA = 'eidolon-model-probe-inspection/1'
PLAN_FIELDS = {'schema', 'suite', 'status', 'input_origin', 'endpoint_implementation',
               'configuration', 'repetitions', 'expected_cases', 'max_planner_attempts',
               'criteria', 'cases', 'fingerprints', 'authorizes_execution',
               'hardware_qualified', 'limits', 'fixed_at'}
REPORT_FIELDS = (PLAN_FIELDS - {'status', 'cases', 'fixed_at'}) | {
    'status', 'verdict', 'results', 'started_at', 'recorded_cases', 'started_cases',
    'error_code', 'not_started_cases', 'elapsed_ms', 'finished_at'}
RESULT_FIELDS = {'outcome', 'failed_checks', 'mission_status', 'mission_error_code',
                 'planner_attempts', 'verified_tool_calls', 'id', 'mission_id',
                 'state_directory', 'elapsed_ms'}
FAILED_CHECKS = {'SOURCE_LABELS_PRESERVED', 'EMPTY_BLOCKED', 'EMPTY_NOT_PLANNED',
                 'MISSION_ACHIEVED', 'ONE_PLANNER_ATTEMPT', 'SOURCE_COUNT',
                 'VERIFIED_PURE_TOOL', 'EXACT_SOURCE_RESULTS', 'RESULT_SOURCES_PRESERVED',
                 'COMPLETED_RESUME_CHANGED'}
MISSION_STATES = {'NEW', 'RUNNING', 'BLOCKED', 'FAILED', 'SUCCEEDED', 'CANCELLED',
                  'ABANDONED', 'REVIEW_REQUIRED'}


class ProbeInspectionError(ValueError):
    pass


def _read(path):
    try:
        return load(read_report(path))
    except (QualificationCheckError, ReportError):
        raise ProbeInspectionError('PROBE_DOCUMENT_UNREADABLE') from None


def _exists(path):
    # A dangling link is present and must be rejected by the bounded reader.
    return os.path.lexists(path)


def _require(condition):
    if not condition:
        raise ProbeInspectionError('PROBE_DOCUMENT_INCONSISTENT')


def _count(value, maximum):
    return type(value) is int and 0 <= value <= maximum


def _elapsed(value):
    # A generous finite bound also rejects integers too large for float conversion.
    return type(value) in {int, float} and 0 <= value <= 1e12


def _timestamp(value):
    if type(value) is not str or len(value) > 100:
        return False
    try:
        return datetime.fromisoformat(value).tzinfo is not None
    except ValueError:
        return False


def _plan(plan):
    _require(type(plan) is dict and set(plan) == PLAN_FIELDS)
    _require(plan.get('schema') == SCHEMA and plan.get('suite') == SUITE)
    _require(plan.get('status') == 'PLANNED' and plan.get('input_origin') == 'synthetic')
    _require(plan.get('endpoint_implementation') == 'unverified')
    _require(plan.get('authorizes_execution') is False and plan.get('hardware_qualified') is False)
    _require(type(plan.get('repetitions')) is int and 1 <= plan['repetitions'] <= 5)
    _require(plan.get('expected_cases') == 4 * plan['repetitions']
             and type(plan.get('expected_cases')) is int)
    _require(plan.get('max_planner_attempts') == 3 * plan['repetitions']
             and type(plan.get('max_planner_attempts')) is int)
    _require(digest(plan.get('cases')) == digest(corpus())
             and digest(plan.get('criteria')) == digest(CRITERIA))
    _require(_timestamp(plan.get('fixed_at')))
    config = plan.get('configuration')
    _require(type(config) is dict and set(config) == {
        'model_id', 'manifest', 'core_version', 'tools', 'policy', 'call_seconds', 'max_invocations_per_case'})
    _require(type(config.get('model_id')) is str
             and 1 <= len(config['model_id']) <= 400)
    _require(not any(ord(c) < 32 or ord(c) == 127 for c in config['model_id']))
    _require(type(config['core_version']) is str and 1 <= len(config['core_version']) <= 40)
    _require(config['tools'] == default_registry().manifest() and config['policy'] == Policy().manifest())
    _require(type(config['call_seconds']) in {int, float} and 0 < config['call_seconds'] <= 300)
    _require(type(config['max_invocations_per_case']) is int and config['max_invocations_per_case'] == CALL_BUDGET)
    manifest = config['manifest']
    _require(type(manifest) is dict and type(manifest.get('adapter')) is str
             and manifest['adapter'] in {'ollama-chat/4', 'openai-chat-llamacpp/4'})
    _require(type(manifest.get('model')) is str and 1 <= len(manifest['model']) <= 200)
    prefix = 'ollama' if manifest['adapter'] == 'ollama-chat/4' else 'openai-chat'
    _require(config['model_id'] == f"{prefix}/{manifest['model']}@{digest(manifest)[:16]}")
    _require(plan.get('fingerprints') == {
        'corpus_sha256': digest(plan['cases']), 'criteria_sha256': digest(plan['criteria']),
        'configuration_sha256': digest(config)})


def _result(value, identity, case):
    _require(type(value) is dict and set(value) == RESULT_FIELDS)
    _require(value['id'] == identity and value['state_directory'] == 'state-' + identity)
    _require(type(value['mission_id']) is str and re.fullmatch(r'm-[0-9a-f]{32}', value['mission_id']) is not None)
    _require(type(value['outcome']) is str and value['outcome'] in {'PASS', 'FAIL', 'ERROR'})
    _require(type(value['mission_status']) is str and value['mission_status'] in MISSION_STATES)
    code = value['mission_error_code']
    _require(code is None or type(code) is str and re.fullmatch(r'[A-Z][A-Z0-9_]{0,79}', code) is not None)
    failed = value['failed_checks']
    _require(type(failed) is list and len(failed) <= 16
             and all(type(c) is str and c in FAILED_CHECKS for c in failed))
    _require(_count(value['planner_attempts'], 1) and _count(value['verified_tool_calls'], 5))
    elapsed = value['elapsed_ms']
    _require(_elapsed(elapsed))
    if value['outcome'] == 'PASS':
        _require(not failed)
        if case == 'empty':
            _require(value['mission_status'] == 'BLOCKED' and code == 'MEMORY_EMPTY'
                     and value['planner_attempts'] == 0 and value['verified_tool_calls'] == 0)
        else:
            _require(value['mission_status'] == 'SUCCEEDED' and code is None
                     and value['planner_attempts'] == 1
                     and value['verified_tool_calls'] == (2 if case == 'unicode-multiple' else 1))
    if value['outcome'] == 'FAIL':
        _require(bool(failed))
    if value['outcome'] == 'ERROR':
        _require(code is not None)


def inspect_probe(directory):
    root = Path(directory)
    try:
        info = root.lstat()
        if not stat.S_ISDIR(info.st_mode):
            raise ProbeInspectionError('PROBE_DIRECTORY_REQUIRED')
    except OSError:
        raise ProbeInspectionError('PROBE_DIRECTORY_UNAVAILABLE') from None
    marker = _exists(root / INCOMPLETE)
    if marker:
        _require(digest(_read(root / INCOMPLETE)) == digest({'status': 'INCOMPLETE', 'resume_allowed': False}))
    summary = {
        'schema': INSPECTION_SCHEMA, 'status': 'INCOMPLETE', 'code': 'PROBE_INCOMPLETE',
        'recorded_cases': 0, 'expected_cases': None, 'started_cases': None,
        'unrecorded_cases_may_have_started': True, 'incomplete_marker': marker,
        'reported_verdict': None, 'results': [], 'fingerprints': None,
        'server_contacted': False, 'authorizes_execution': False,
        'mission_evidence_rechecked': False, 'hardware_qualified': False,
        'limits': ['Document consistency only; mission SQLite evidence and telemetry authenticity are not verified.',
                   'No call is resumed. An unrecorded case may already have contacted the endpoint.',
                   'Read after the writer has stopped; this is not an atomic cross-file snapshot.'],
    }
    if not _exists(root / 'plan.json'):
        if marker:
            summary['code'] = 'PROBE_PLAN_MISSING'
            return summary
        raise ProbeInspectionError('NOT_A_PROBE_DIRECTORY')
    plan = _read(root / 'plan.json')
    _plan(plan)
    summary.update(expected_cases=plan['expected_cases'], fingerprints=plan['fingerprints'],
                   model_id=plan['configuration']['model_id'])
    results = summary['results']
    gap = False
    for repetition in range(1, plan['repetitions'] + 1):
        for case in ('single', 'unicode-multiple', 'instruction-in-data', 'empty'):
            identity = f'{case}-{repetition}'
            path = root / ('case-' + identity + '.json')
            if not _exists(path):
                gap = True
                continue
            _require(not gap)  # No later case may leap over missing evidence.
            result = _read(path)
            _result(result, identity, case)
            results.append(result)
    summary['recorded_cases'] = len(results)
    _require(len({r['mission_id'] for r in results}) == len(results))
    _require(not any(r['outcome'] == 'ERROR' for r in results[:-1]))
    if not _exists(root / 'report.json'):
        summary['code'] = 'PROBE_REPORT_MISSING'
        return summary
    report = _read(root / 'report.json')
    _require(type(report) is dict and set(report) == REPORT_FIELDS)
    for key, value in plan.items():
        if key not in {'status', 'cases', 'fixed_at'}:
            _require(digest(report.get(key)) == digest(value))
    _require(digest(report.get('results')) == digest(results) and type(report.get('recorded_cases')) is int
             and report['recorded_cases'] == len(results))
    _require(type(report.get('started_cases')) is int and report['started_cases'] == len(results))
    _require(type(report.get('not_started_cases')) is int
             and report['not_started_cases'] == plan['expected_cases'] - len(results))
    _require(_timestamp(report.get('started_at')) and _timestamp(report.get('finished_at')))
    _require(report['started_at'] == plan['fixed_at'])
    _require(datetime.fromisoformat(plan['fixed_at']) <= datetime.fromisoformat(report['finished_at']))
    _require(_elapsed(report.get('elapsed_ms')))
    _require(type(report.get('status')) is str and report['status'] in {'COMPLETE', 'STOPPED'})
    if report['status'] == 'COMPLETE':
        _require(len(results) == plan['expected_cases'] and report.get('error_code') is None)
        _require(all(r['outcome'] != 'ERROR' for r in results))
    else:
        _require(bool(results) and results[-1]['outcome'] == 'ERROR'
                 and report.get('error_code') == 'PROBE_CASE_ERROR')
    verdict = 'PASSED_CASES' if all(r['outcome'] == 'PASS' for r in results) else 'FAILED_CASES'
    _require(report.get('verdict') == verdict)
    summary.update(reported_verdict=verdict, started_cases=report['started_cases'])
    if not marker:
        summary.update(status='CONSISTENT', code='PROBE_DOCUMENTS_CONSISTENT',
                       unrecorded_cases_may_have_started=False, run_status=report['status'])
    return summary


def render_inspection(result):
    level = 'INFO' if result['status'] == 'CONSISTENT' else 'ATTENTION'
    lines = [header(title='Consultation de la recette'), message(level, result['code']),
             message('INFO', f"Bilans enregistrés : {result['recorded_cases']} ; attendus : {result['expected_cases']}.")]
    if result['reported_verdict'] is not None:
        lines.append(message('INFO', 'Verdict du rapport : ' + result['reported_verdict']))
    for case in result['results']:
        lines.append(message('INFO', case['id'] + ' : ' + case['outcome']))
    if result['unrecorded_cases_may_have_started']:
        lines.append(message('ATTENTION', 'Essai incomplet : un cas sans bilan peut avoir commencé ; aucune relance effectuée.'))
    lines.append(message('ATTENTION', 'Cohérence des documents uniquement ; preuves SQLite et matériel non revérifiés.'))
    return '\n'.join(lines)

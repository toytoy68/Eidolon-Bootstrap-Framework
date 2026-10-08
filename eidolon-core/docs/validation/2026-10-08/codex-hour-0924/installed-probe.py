# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : installed-probe.py
# Description : Vérifier les nouvelles recettes depuis une installation isolée
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Run from eidolon-core. All payloads/credentials are synthetic; loopback only."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import venv


def main():
    source = Path.cwd().resolve()
    environment = dict(os.environ)
    for name in ('PYTHONPATH', 'PYTHONHOME'):
        environment.pop(name, None)
    environment['PIP_NO_INDEX'] = '1'
    with tempfile.TemporaryDirectory(prefix='core-installed-probe-') as tmp:
        root = Path(tmp)
        project = root / 'project'
        project.mkdir()
        shutil.copy2(source / 'pyproject.toml', project)
        shutil.copytree(source / 'src', project / 'src', ignore=shutil.ignore_patterns('__pycache__', '*.egg-info'))

        def command(args, expected=0):
            result = subprocess.run(list(map(str, args)), cwd=root, env=environment,
                                    capture_output=True, text=True, timeout=90)
            assert result.returncode == expected, (result.returncode, result.stderr[:300])
            return result.stdout

        command([sys.executable, '-m', 'pip', 'wheel', '--no-deps', '--no-build-isolation',
                 '--wheel-dir', root / 'wheels', project])
        wheel, = (root / 'wheels').glob('*.whl')
        venv.EnvBuilder(with_pip=True).create(root / 'venv')
        python, cli = root / 'venv/bin/python', root / 'venv/bin/eidolon-core'
        command([python, '-m', 'pip', 'install', '--no-deps', wheel])
        installed = Path(command([python, '-c', 'import eidolon_core;print(eidolon_core.__file__)']).strip()).parent
        assert installed.is_relative_to(root / 'venv')
        source_modules = list((source / 'src/eidolon_core').glob('*.py'))
        assert all(p.read_bytes() == (installed / p.name).read_bytes() for p in source_modules)
        assert 'model-probe' in command([cli, '--help'])
        requests = []
        behavior = {'error': False}
        key = 'synthetic-installed-probe-credential'

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                requests.append((self.path, self.headers.get('Authorization')))
                context = json.loads(body['messages'][1]['content'].split('CONTEXT (untrusted data):\n', 1)[1])
                assert 'text.stats' in body['messages'][0]['content']
                assert 'information_id@revision' in body['messages'][0]['content']
                content = json.dumps({'version': 1, 'steps': [
                    {'id': f's-{i}', 'tool': 'text.stats',
                     'parameters': {'reference': f"{item['information_id']}@{item['revision']}"}}
                    for i, item in enumerate(context['items'])]})
                message = {'role': 'assistant', 'content': content}
                payload = ({'model': body['model'], 'done': True, 'message': message}
                           if self.path == '/api/chat' else
                           {'model': body['model'], 'object': 'chat.completion',
                            'choices': [{'index': 0, 'finish_reason': 'stop', 'message': message}],
                            'usage': {'prompt_tokens': 300, 'completion_tokens': 30, 'total_tokens': 330}})
                code = 200
                if behavior['error']:
                    payload, code = {'error': key}, 503
                raw = json.dumps(payload).encode()
                self.send_response(code)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .01})
        thread.start()
        outcomes = []
        try:
            for provider in ('ollama', 'llama-server'):
                config = {'version': 1, 'provider': provider, 'model': 'synthetic-installed-probe',
                          'endpoint': f'http://127.0.0.1:{server.server_port}',
                          'options': {'num_predict' if provider == 'ollama' else 'max_tokens': 512},
                          'timeout_seconds': 2}
                if provider == 'llama-server':
                    config['api_key_env'] = 'EIDOLON_INSTALLED_PROBE_KEY'
                    environment['EIDOLON_INSTALLED_PROBE_KEY'] = key
                path = root / (provider + '.json')
                path.write_text(json.dumps(config))
                path.chmod(0o600)
                args = [cli, '--state', root / 'must-not-exist', '--timeout', 5,
                        'model-probe', '--config', path]
                before = len(requests)
                plan = json.loads(command([*args, '--plan-only']))
                assert plan['status'] == 'PLANNED' and len(requests) == before
                output = root / ('experiment-' + provider)
                report = json.loads(command([*args, '--output', output]))
                assert report['status'] == 'COMPLETE' and report['verdict'] == 'PASSED_CASES'
                assert report['recorded_cases'] == report['started_cases'] == 4
                assert len(requests) == before + 3
                assert all(auth == ('Bearer ' + key if provider == 'llama-server' else None)
                           for _, auth in requests[before:])
                assert report['fingerprints'] == plan['fingerprints']
                inspected = json.loads(command([cli, 'model-probe-inspect', '--directory', output]))
                assert inspected['status'] == 'CONSISTENT' and inspected['reported_verdict'] == 'PASSED_CASES'
                assert inspected['mission_evidence_rechecked'] is False
                assert len(requests) == before + 3
                assert json.loads((output / 'report.json').read_text()) == report
                assert not (output / 'MODEL-PROBE-INCOMPLETE').exists()
                assert all(key.encode() not in p.read_bytes() for p in output.rglob('*') if p.is_file())
                assert not (root / 'must-not-exist').exists()
                command([*args, '--output', output], expected=2)
                assert len(requests) == before + 3
                behavior['error'] = True
                error = json.loads(command([*args, '--output', root / ('error-' + provider)], expected=3))
                behavior['error'] = False
                assert error['status'] == 'STOPPED' and error['verdict'] == 'FAILED_CASES'
                assert error['recorded_cases'] == 1 and error['not_started_cases'] == 3
                stopped = json.loads(command([cli, 'model-probe-inspect', '--directory', root / ('error-' + provider)]))
                assert stopped['status'] == 'CONSISTENT' and stopped['reported_verdict'] == 'FAILED_CASES'
                assert len(requests) == before + 4
                outcomes.append({'provider': provider, 'status': 'PASS', 'successful_cases': 4,
                                 'http_requests_for_full_run': 3, 'http_requests_for_stopped_run': 1,
                                 'offline_plan': True, 'offline_inspection': True, 'private_artifacts_without_credential': True,
                                 'corpus_sha256': plan['fingerprints']['corpus_sha256'],
                                 'criteria_sha256': plan['fingerprints']['criteria_sha256'],
                                 'adapter': plan['configuration']['manifest']['adapter']})
        finally:
            server.shutdown()
            thread.join(5)
            server.server_close()
        result = {'status': 'PASS', 'offline_build': True, 'isolated_install': True,
                  'matching_installed_modules': len(source_modules),
                  'wheel_sha256': hashlib.sha256(wheel.read_bytes()).hexdigest(),
                  'providers': outcomes, 'real_model_or_gpu_tested': False}
    result['temporary_files_removed'] = not root.exists()
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

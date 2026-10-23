"""Offline regression suite; no model downloads or GPU required."""
import argparse
import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('eidolon_video', ROOT / 'eidolon_video.py')
video = importlib.util.module_from_spec(spec)
spec.loader.exec_module(video)
WORKFLOWS = list((ROOT / 'workflows').glob('*.json'))


def workflow(fragment='14b-gguf-v100'):
    return json.loads(next(p for p in WORKFLOWS if fragment in p.name).read_text())


def options(**kw):
    defaults = dict(negative=None, seed=42, width=None, height=None, length=None,
                    fps=None, prefix=None, steps=None, set=None)
    defaults.update(kw)
    return argparse.Namespace(**defaults)


def output_entry(filename='clip.mp4'):
    return {'outputs': {'14': {'images': [{'filename': filename,
                                         'subfolder': 'eidolon', 'type': 'output'}]}}}


class ClientTests(unittest.TestCase):
    def test_default_unloads_ollama(self):
        with patch.object(video, 'http_json', return_value={'response': 'prompt'}) as request:
            self.assertEqual(video.enhance_prompt('idea', 'http://local', 'qwen'), 'prompt')
        self.assertEqual(request.call_args.args[1]['keep_alive'], 0)

    def test_separate_gpu_can_keep_model(self):
        with patch.object(video, 'http_json', return_value={'response': 'prompt'}) as request:
            video.enhance_prompt('idea', 'http://local', 'qwen', '5m')
        self.assertEqual(request.call_args.args[1]['keep_alive'], '5m')

    def test_old_ollama_retry_preserves_unload(self):
        calls = []
        def request(url, data, **kw):
            calls.append(dict(data))
            if len(calls) == 1:
                raise urllib.error.HTTPError(url, 400, 'unsupported think', {}, io.BytesIO())
            return {'response': '<think>secret</think>fox'}
        with patch.object(video, 'http_json', side_effect=request):
            self.assertEqual(video.enhance_prompt('idea', 'http://local', 'qwen'), 'fox')
        self.assertNotIn('think', calls[1])
        self.assertEqual(calls[1]['keep_alive'], 0)

    def test_all_default_graphs_valid(self):
        for path in WORKFLOWS:
            with self.subTest(path=path.name):
                wf = json.loads(path.read_text())
                video.validate_workflow(wf)
                video.prepare_workflow(wf, options(), 'new prompt')
                self.assertTrue(all(n['inputs']['text'] == 'new prompt'
                                    for n in video.nodes_by_title(wf, 'Positive')))

    def test_steps_keep_high_low_continuity(self):
        for steps in (2, 3, 4, 20, 31):
            with self.subTest(steps=steps):
                wf = workflow()
                video.apply_steps(wf, steps)
                video.validate_workflow(wf)
                hi, lo = wf['10']['inputs'], wf['11']['inputs']
                self.assertEqual(hi['end_at_step'], lo['start_at_step'])
                self.assertLess(lo['start_at_step'], steps)
                self.assertEqual(hi['steps'], lo['steps'])

    def test_reject_empty_high_low_pass(self):
        for steps in (-1, 0, 1):
            with self.subTest(steps=steps), self.assertRaises(ValueError):
                video.apply_steps(workflow(), steps)

    def test_single_sampler_one_step(self):
        wf = workflow('5b')
        video.apply_steps(wf, 1)
        video.validate_workflow(wf)

    def test_invalid_geometry(self):
        for fragment, overrides in [('5b', {'width': 831}), ('5b', {'height': 481}),
                                    ('14b-gguf-v100', {'width': 830}),
                                    ('5b', {'length': 72}), ('5b', {'length': -3}),
                                    ('5b', {'fps': float('nan')}), ('5b', {'fps': 0})]:
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                video.prepare_workflow(workflow(fragment), options(**overrides), 'test')

    def test_set_cannot_bypass_geometry(self):
        with self.assertRaises(ValueError):
            video.prepare_workflow(workflow('5b'), options(set=['7.width=831']), 'test')

    def test_set_rejects_typo(self):
        with self.assertRaises(ValueError):
            video.prepare_workflow(workflow(), options(set=['1.unet_nam=missing']), 'test')

    def test_set_model_name(self):
        wf = video.prepare_workflow(workflow(), options(set=['1.unet_name=test.gguf']), 'test')
        self.assertEqual(wf['1']['inputs']['unet_name'], 'test.gguf')

    def test_bad_graph_link(self):
        wf = workflow()
        wf['10']['inputs']['model'] = ['missing', 0]
        with self.assertRaises(ValueError):
            video.validate_workflow(wf)

    def test_download_rejects_paths(self):
        with tempfile.TemporaryDirectory() as d, patch.object(video.urllib.request, 'urlopen') as request:
            for name in ('../outside.mp4', '/tmp/outside.mp4', 'a/b.mp4', r'..\outside.mp4',
                         r'C:\outside.mp4', 'x:stream', '.', '..', '', '\0bad'):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    video.download_outputs('http://local', output_entry(name), Path(d))
            request.assert_not_called()
            self.assertEqual(list(Path(d).iterdir()), [])

    def test_download_preserves_existing_file(self):
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / 'clip.mp4'
            dest.write_bytes(b'original')
            with self.assertRaises(FileExistsError):
                video.download_outputs('http://local', output_entry(), Path(d))
            self.assertEqual(dest.read_bytes(), b'original')

    def test_download_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'out'; out.mkdir()
            target = Path(d) / 'target'; target.write_bytes(b'original')
            (out / 'clip.mp4').symlink_to(target)
            with self.assertRaises(FileExistsError):
                video.download_outputs('http://local', output_entry(), out)
            self.assertEqual(target.read_bytes(), b'original')

    def test_download_removes_failed_partial(self):
        with tempfile.TemporaryDirectory() as d, patch.object(video.urllib.request, 'urlopen',
                                                             side_effect=OSError('connection lost')):
            with self.assertRaises(OSError):
                video.download_outputs('http://local', output_entry(), Path(d))
            self.assertEqual(list(Path(d).iterdir()), [])

    def test_download_streams(self):
        class Bounded(io.BytesIO):
            def read(self, size=-1):
                if size <= 0:
                    raise AssertionError('unbounded read')
                return super().read(size)
        with tempfile.TemporaryDirectory() as d, patch.object(video.urllib.request, 'urlopen',
                                                             return_value=Bounded(b'video')):
            paths = video.download_outputs('http://local', output_entry(), Path(d))
            self.assertEqual(paths[0].read_bytes(), b'video')

    def test_history_missing_completed_does_not_succeed(self):
        hist = {'id': {'status': {}, 'outputs': {}}}
        with patch.object(video, 'http_json', return_value=hist), \
             patch.object(video.time, 'monotonic', side_effect=[0, 0, 0, 2]), \
             patch.object(video.time, 'sleep'), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaisesRegex(SystemExit, "n'a pas été annulée"):
                video.wait('http://local', 'id', 1)

    def test_execution_error_reported(self):
        hist = {'id': {'status': {'status_str': 'error', 'messages': [
            ['execution_error', {'node_id': '10', 'node_type': 'KSamplerAdvanced',
                                 'exception_message': 'CUDA out of memory'}]]}}}
        with patch.object(video, 'http_json', return_value=hist):
            with self.assertRaisesRegex(SystemExit, 'CUDA out of memory'):
                video.wait('http://local', 'id', 1)

    def test_cli_dry_runs(self):
        for path in WORKFLOWS:
            with self.subTest(path=path.name):
                result = subprocess.run([sys.executable, str(ROOT / 'eidolon_video.py'),
                                         '-w', str(path), '-p', 'test', '--dry-run', '--seed', '1'],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                video.validate_workflow(json.loads(result.stdout))

    def test_cli_invalid_timeout(self):
        result = subprocess.run([sys.executable, str(ROOT / 'eidolon_video.py'),
                                 '-w', str(WORKFLOWS[0]), '-p', 'test', '--timeout', 'nan'],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('--timeout', result.stderr)

    def test_http_end_to_end(self):
        events = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def reply(self, payload):
                body = json.dumps(payload).encode()
                self.send_response(200); self.end_headers(); self.wfile.write(body)
            def do_POST(self):
                data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                events.append((self.path, data))
                if self.path == '/api/generate':
                    self.reply({'response': 'A fox in snow'})
                else:
                    self.reply({'prompt_id': 'test-id'})
            def do_GET(self):
                if self.path.startswith('/history/'):
                    entry = output_entry(); entry['status'] = {'completed': True, 'status_str': 'success'}
                    self.reply({'test-id': entry})
                else:
                    self.send_response(200); self.end_headers(); self.wfile.write(b'fake-mp4')
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            url = f'http://127.0.0.1:{server.server_port}'
            with tempfile.TemporaryDirectory() as d:
                result = subprocess.run([sys.executable, str(ROOT / 'eidolon_video.py'),
                                         '-w', str(WORKFLOWS[0]), '-p', 'fox', '--enhance',
                                         '--ollama-url', url, '--server', url, '--out', d],
                                        capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(Path(result.stdout.strip()).read_bytes(), b'fake-mp4')
                self.assertEqual(events[0][1]['keep_alive'], 0)
                positive = video.nodes_by_title(events[1][1]['prompt'], 'Positive')
                self.assertEqual(positive[0]['inputs']['text'], 'A fox in snow')
        finally:
            server.shutdown(); server.server_close(); thread.join()


class InstallerTests(unittest.TestCase):
    def test_pin_checkout_keeps_revision_and_rejects_dirty_tree(self):
        import os
        with tempfile.TemporaryDirectory() as d:
            origin, dest = Path(d) / 'origin', Path(d) / 'checkout'
            def git(*args, cwd=None):
                return subprocess.check_output(['git', *args], cwd=cwd, stderr=subprocess.DEVNULL,
                                               text=True).strip()
            git('init', str(origin))
            git('config', 'user.name', 'Test', cwd=origin)
            git('config', 'user.email', 'test@example.invalid', cwd=origin)
            (origin / 'file').write_text('first')
            git('add', '.', cwd=origin); git('commit', '-m', 'first', cwd=origin)
            first = git('rev-parse', 'HEAD', cwd=origin)
            (origin / 'file').write_text('second')
            git('commit', '-am', 'second', cwd=origin)
            git('clone', str(origin), str(dest))
            env = dict(os.environ, INSTALLER=str(ROOT / 'install-comfyui.sh'),
                       LOGFILE=str(Path(d) / 'log'), DEST=str(dest), REV=first)
            command = 'source "$INSTALLER"; as_user() { "$@"; }; pin_checkout "$DEST" "$REV"'
            result = subprocess.run(['bash', '-c', command], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(git('rev-parse', 'HEAD', cwd=dest), first)
            (dest / 'file').write_text('local edits')
            result = subprocess.run(['bash', '-c', command], env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((dest / 'file').read_text(), 'local edits')

    def test_torch_constraints_persist_for_future_pip(self):
        import os
        with tempfile.TemporaryDirectory() as d:
            comfy = Path(d) / 'comfy'; (comfy / 'venv' / 'bin').mkdir(parents=True)
            pip = comfy / 'venv' / 'bin' / 'pip'
            pip.write_text('''#!/bin/bash
echo "$*" >> "$PIP_CALLS"
if [[ "$1" == freeze ]]; then
    printf 'torch==2.14.0+cu126\\ntorchvision==0.29.0+cu126\\ntorchaudio==2.14.0+cu126\\nother==1.0\\n'
fi
''')
            pip.chmod(0o755)
            env = dict(os.environ, INSTALLER=str(ROOT / 'install-comfyui.sh'),
                       LOGFILE=str(Path(d) / 'log'), COMFY_DIR=str(comfy), PIP_CALLS=str(Path(d) / 'calls'))
            result = subprocess.run(['bash', '-c', 'source "$INSTALLER"; as_user() { "$@"; }; install_torch'],
                                    env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            locked = (comfy / 'eidolon-constraints.txt').read_text()
            self.assertIn('torch==2.14.0+cu126', locked)
            self.assertNotIn('other', locked)
            calls = Path(env['PIP_CALLS']).read_text()
            self.assertIn('config --site set global.constraint', calls)
            self.assertIn('config --site set global.extra-index-url', calls)

    def test_gpu_validation_checks_all_devices_and_rejects_nan(self):
        import types
        script = (ROOT / 'install-comfyui.sh').read_text()
        code = script.split("<<'PY' 2>&1\n", 1)[1].split('\nPY\n', 1)[0]
        class Tensor:
            def __matmul__(self, other): return self
            def abs(self): return self
            def sum(self): return self
            def item(self): return 1
        cuda = types.SimpleNamespace(is_available=lambda: True, get_arch_list=lambda: ['sm_70'],
                device_count=lambda: 2, synchronize=lambda i: None,
                get_device_properties=lambda i: types.SimpleNamespace(name='V100', major=7,
                                                                       minor=0, total_memory=16*2**30))
        devices = []
        def randn(*args, device, dtype):
            devices.append(device); return Tensor()
        torch = types.SimpleNamespace(cuda=cuda, __version__='test', version=types.SimpleNamespace(cuda='12.6'),
                                      float16='fp16', randn=randn,
                                      isfinite=lambda y: types.SimpleNamespace(all=lambda: Tensor()))
        with patch.dict(sys.modules, {'torch': torch}), contextlib.redirect_stdout(io.StringIO()):
            exec(code, {})
        self.assertEqual(devices, ['cuda:0', 'cuda:1'])
        torch.isfinite = lambda y: types.SimpleNamespace(all=lambda: types.SimpleNamespace(item=lambda: False))
        with patch.dict(sys.modules, {'torch': torch}), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(AssertionError, 'non fini'):
                exec(code, {})

    def harness(self, fail=False):
        with tempfile.TemporaryDirectory() as d:
            script = '''
source "$INSTALLER"
for name in title check_root check_user check_nvidia install_packages check_network create_directories install_comfyui install_venv install_torch install_requirements install_custom_nodes create_model_directories summary; do
    eval "$name() { echo $name; }"
done
run() { echo "run:$1"; }
configure_service() { echo SERVICE_ENABLED; }
validate_torch() { echo GPU_VALIDATION; return "$FAIL_GPU"; }
main
'''
            import os
            env = dict(os.environ, INSTALLER=str(ROOT / 'install-comfyui.sh'),
                       LOGFILE=str(Path(d) / 'install.log'), FAIL_GPU='1' if fail else '0')
            return subprocess.run(['bash', '-c', script], env=env, capture_output=True, text=True)

    def test_failed_validation_never_enables_service(self):
        result = self.harness(fail=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('SERVICE_ENABLED', result.stdout)

    def test_success_enables_only_after_validation(self):
        result = self.harness()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLess(result.stdout.index('GPU_VALIDATION'), result.stdout.index('SERVICE_ENABLED'))
        self.assertLess(result.stdout.index('install_packages'), result.stdout.index('check_network'))

    def test_shell_syntax(self):
        for path in list(ROOT.glob('*.sh')) + [ROOT / 'sources.lock']:
            with self.subTest(path=path.name):
                result = subprocess.run(['bash', '-n', str(path)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()

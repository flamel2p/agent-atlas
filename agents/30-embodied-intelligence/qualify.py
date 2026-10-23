"""Rerun fixture qualification from a copied case and an isolated wheel install.

Only this directory is copied. The installed-wheel interpreter runs with -I and
an unrelated cwd, so repository imports cannot satisfy missing package files.
Temporary environments and build artifacts disappear when the script finishes.
"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


CASE = Path(__file__).resolve().parent
EXPECTED = {'normal': (0, 'complete'), 'replan': (0, 'complete'),
            'emergency': (0, 'halted'), 'obstacle': (1, 'fault'),
            'replay': (0, 'complete'), 'tick-limit': (1, 'limit')}


def execute(arguments: list[str], cwd: Path, environment: dict[str, str], code: int = 0):
    result = subprocess.run(arguments, cwd=cwd, env=environment, capture_output=True, timeout=60)
    if result.returncode != code:
        raise RuntimeError(f'Qualification subprocess failed with code {result.returncode}: {result.stderr.decode()}')
    return result


def cli_checks(prefix: list[str], cwd: Path, environment: dict[str, str]) -> None:
    for name, (code, outcome) in EXPECTED.items():
        result = execute([*prefix, '--fixture', name], cwd, environment, code)
        report = json.loads(result.stdout)
        assert report['outcome'] == outcome, name
        assert not result.stderr, name
        if name == 'normal':
            assert (report['final_state']['position'], report['final_state']['battery'],
                    report['final_state']['version'], report['ticks']) == (7, 19, 4, 4)
        if name == 'emergency':
            assert [effect['kind'] for effect in report['effects']] == ['command', 'emergency_stop']
    assert b'embodied-cart' in execute([*prefix, '--help'], cwd, environment).stdout


def main() -> None:
    environment = dict(os.environ)
    environment.pop('PYTHONPATH', None)
    environment.pop('PYTHONHOME', None)
    environment.pop('VIRTUAL_ENV', None)
    environment['UV_CACHE_DIR'] = '/tmp/agent-atlas-uv-cache'
    environment['UV_PYTHON_DOWNLOADS'] = 'never'
    with tempfile.TemporaryDirectory(prefix='atlas-cart-') as temporary:
        root = Path(temporary)
        copied = root / 'case'
        outside = root / 'outside'
        outside.mkdir()
        shutil.copytree(CASE, copied, ignore=shutil.ignore_patterns('.venv', '__pycache__', 'dist', '.audit', '*.pyc'))
        execute(['uv', 'sync', '--offline', '--locked', '--project', str(copied)], outside, environment)
        copied_python = copied / '.venv/bin/python'
        result = execute([str(copied_python), '-I', '-m', 'unittest', 'discover', '-s', str(copied / 'tests')],
                         outside, environment)
        print('Case-only copy tests passed. ' + result.stderr.decode().strip().splitlines()[-1])
        cli_checks([str(copied_python), '-I', '-m', 'embodied_intelligence'], outside, environment)
        cli_checks([str(copied / '.venv/bin/embodied-cart')], outside, environment)
        print('Case-only module and console entry points passed all six fixtures and help.')
        wheels = root / 'wheels'
        execute(['uv', 'build', '--offline', '--wheel', '--out-dir', str(wheels), str(copied)], outside, environment)
        wheel = next(wheels.glob('*.whl'))
        installed = root / 'installed'
        execute(['uv', 'venv', '--offline', '--python', '3.14', str(installed)], outside, environment)
        python = installed / 'bin/python'
        execute(['uv', 'pip', 'install', '--offline', '--python', str(python), str(wheel)], outside, environment)
        wheel_tests = outside / 'tests'
        shutil.copytree(copied / 'tests', wheel_tests, ignore=shutil.ignore_patterns('__pycache__'))
        # Move the build source away before exercising the installed resource loader.
        shutil.rmtree(copied)
        result = execute([str(python), '-I', '-c',
                          'import embodied_intelligence; print(embodied_intelligence.__file__)'], outside, environment)
        assert str(installed).encode() in result.stdout
        assert b'site-packages' in result.stdout
        cli_checks([str(python), '-I', '-m', 'embodied_intelligence'], outside, environment)
        cli_checks([str(installed / 'bin/embodied-cart')], outside, environment)
        result = execute([str(python), '-I', '-m', 'unittest', 'discover', '-s', str(wheel_tests)], outside, environment)
        print('Installed wheel tests passed. ' + result.stderr.decode().strip().splitlines()[-1])
        print('Installed wheel module and console entry points passed all six fixtures and help outside the repository.')


if __name__ == '__main__':
    main()

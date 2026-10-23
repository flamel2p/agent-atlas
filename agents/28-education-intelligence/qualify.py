"""Rerun fixture qualification in-source, in a case-only copy, and from a wheel.

Temporary copies and virtual environments live outside the repository. Every
subprocess has a timeout and removes PYTHONPATH, so sibling installations cannot
supply missing case resources. This checks isolation, not a live provider.
"""

import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
ENV = {key: value for key, value in os.environ.items() if key not in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV")}
ENV['UV_CACHE_DIR'] = '/tmp/agent-atlas-uv-cache'
ENV['UV_OFFLINE'] = '1'


def command(arguments: list[str], cwd: Path) -> subprocess.CompletedProcess:
    result = subprocess.run(arguments, cwd=cwd, env=ENV, capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise RuntimeError(f"Qualification command failed: {arguments[0]}\n{result.stdout}\n{result.stderr}")
    return result


def check_report(arguments: list[str], cwd: Path):
    report = json.loads(command(arguments, cwd).stdout)
    if report['eligible'] != ['add', 'count'] or report['next_activity']['kind'] != 'review':
        raise RuntimeError('CLI fixture acceptance failed')


def test_suite(arguments: list[str], cwd: Path) -> int:
    result = command(arguments, cwd)
    match = re.search(r'Ran (\d+) tests', result.stderr)
    if match is None:
        raise RuntimeError('Test runner did not report its executed test count')
    return int(match.group(1))


def main():
    source_count = test_suite([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'], ROOT)
    check_report([str(ROOT/'.venv/bin/education-demo')], ROOT)
    with tempfile.TemporaryDirectory(prefix='atlas-education-', dir='/tmp') as directory:
        external = Path(directory)
        copied = external/'case'
        shutil.copytree(ROOT, copied, ignore=shutil.ignore_patterns('.venv', '__pycache__', 'dist', '.audit', '*.pyc'))
        command(['uv', 'sync', '--locked', '--offline', '--python', sys.executable], copied)
        copied_python = str(copied/'.venv/bin/python')
        copy_count = test_suite([copied_python, '-m', 'unittest', 'discover', '-s', 'tests', '-v'], copied)
        check_report([str(copied/'.venv/bin/education-demo')], external)
        wheel_dir = external/'wheels'
        command(['uv', 'build', '--offline', '--wheel', '--out-dir', str(wheel_dir)], copied)
        wheels = list(wheel_dir.glob('*.whl'))
        if len(wheels) != 1:
            raise RuntimeError('Expected exactly one wheel')
        installed = external/'installed'
        command(['uv', 'venv', '--python', sys.executable, str(installed)], external)
        wheel_python = str(installed/'bin/python')
        command(['uv', 'pip', 'install', '--offline', '--python', wheel_python, str(wheels[0])], external)
        check_report([str(installed/'bin/education-demo')], external)
        check_report([wheel_python, '-I', '-m', 'education_intelligence'], external)
        # The suite executes against the installed package from an external cwd.
        wheel_count = test_suite([wheel_python, '-I', '-m', 'unittest', 'discover', '-s', str(copied/'tests'), '-v'], external)
        origin = command([wheel_python, '-I', '-c', 'import education_intelligence; print(education_intelligence.__file__)'], external).stdout.strip()
        if str(installed) not in origin:
            raise RuntimeError('Wheel import came from outside its environment')
    print(f'PASS: source {source_count} tests; case-only copy {copy_count} tests; installed wheel {wheel_count} tests; four CLI fixture runs; wheel import isolation.')


if __name__ == '__main__':
    main()

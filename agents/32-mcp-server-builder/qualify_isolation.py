"""Copy this case and its generated server separately; install each own lock.

This is explicit developer setup, outside the build flow. It never reads a model
key or contacts an upstream service. --offline uses a pre-provisioned uv cache.
The generated-only directory has no builder or repository installation.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--offline', action='store_true')
    args = p.parse_args()
    case = Path(__file__).resolve().parent
    workspace = Path(tempfile.mkdtemp(prefix='agent32-independent-', dir='/tmp'))
    builder = workspace / 'builder-only'
    generated = workspace / 'generated-only'
    shutil.copytree(case, builder, ignore=shutil.ignore_patterns('.venv', '__pycache__', '.pytest_cache', 'artifacts'))
    uv = shutil.which('uv')
    if uv is None:
        raise SystemExit('uv_required')
    env = {k: v for k, v in os.environ.items() if k in {'PATH', 'UV_CACHE_DIR'}}
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    commands = []
    def execute(command, cwd):
        commands.append({'command': command, 'cwd': str(cwd)})
        result = subprocess.run(command, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90)
        if result.returncode:
            print(result.stdout.decode(errors='replace')); print(result.stderr.decode(errors='replace'))
            raise SystemExit(result.returncode)
        return result.stdout
    setup = [uv, 'sync', '--locked', '--python', 'python3.14'] + (['--offline'] if args.offline else [])
    execute(setup, builder)
    execute([str(builder / '.venv/bin/python'), '-m', 'mcp_builder.builder', 'build', '--out', 'artifacts/independent'], builder)
    shutil.copytree(builder / 'artifacts/independent/server', generated)
    execute(setup, generated)
    report = json.loads(execute([str(generated / '.venv/bin/python'), 'check_server.py'], generated))
    assert report['result'] == 'passed'
    for path in [generated / 'runtime.py', generated / 'manifest.json', generated / 'pyproject.toml', generated / 'uv.lock']:
        assert 'mcp_builder' not in path.read_text()
        assert str(case) not in path.read_text()
    evidence = {'result': 'passed', 'builder_only': str(builder), 'generated_only': str(generated),
                'commands': commands, 'generated_protocol': report, 'mode': 'fixture', 'live_model': 'not-run', 'real_service': 'not-run'}
    (workspace / 'qualification.json').write_text(json.dumps(evidence, indent=2) + '\n')
    print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    main()

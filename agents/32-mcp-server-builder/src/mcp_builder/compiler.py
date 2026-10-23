"""Bind untrusted design data to host-owned operations and copy fixed code.

BoundToolPlan is constructed only by bind(). The generated manifest is the sole
runtime schema/dispatch table. Hashes bind the exact source snapshots and template
bytes; verification checks the resulting tree again before atomic publication.
"""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import shutil
from .design import PROPOSAL_SCHEMA
from .runtime import validate


def dump(value):
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + '\n'


def digest(data):
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class _BoundToolPlan:
    manifest: dict
    coverage: list


class NeedsInput(Exception):
    pass


def bind(catalog, coverage, policy, proposal, task_ids, hashes):
    validate(PROPOSAL_SCHEMA, proposal)
    tools, names, keys = [], set(), set()
    for selection in proposal['tools']:
        key, name, description = (selection[k] for k in ['operation', 'name', 'description'])
        if key not in catalog or key in keys or not re.fullmatch(r'[a-z][a-z0-9_]{0,63}', name) or name in names or not 1 <= len(description) <= 500:
            raise ValueError('proposal_binding')
        keys.add(key); names.add(name)
        tools.append({**catalog[key], 'name': name, 'description': description})
    mapped = {}
    for association in proposal['tasks']:
        if association['task'] not in task_ids or association['task'] in mapped or association['operation'] not in keys:
            raise ValueError('task_association')
        mapped[association['task']] = association['operation']
    uncovered = proposal['uncovered']
    if len(set(uncovered)) != len(uncovered) or set(uncovered) & set(mapped) or set(uncovered) | set(mapped) != set(task_ids):
        raise ValueError('task_accounting')
    if uncovered or set(policy['required_operations']) - keys or not tools:
        raise NeedsInput('required_task_or_operation_uncovered')
    coverage = [dict(row, status='selected', reason='allowed_supported') if row['operation'] in keys else row for row in coverage]
    manifest = {'version': 1, 'destination': policy['destination'], 'credential_env': policy['credential_env'], 'tools': tools, 'hashes': hashes}
    if len(dump(manifest).encode()) > 65536:
        raise ValueError('bound_manifest_limit')
    return _BoundToolPlan(manifest, coverage)


def emit(plan, staging, checks_raw):
    if not isinstance(plan, _BoundToolPlan):
        raise ValueError('unbound_plan')
    package = Path(__file__).parent
    server = staging / 'server'
    server.mkdir(mode=0o700)
    for source, target in [(package / 'runtime.py', 'runtime.py'), (package / 'check_server.py', 'check_server.py'),
                           (package / 'templates/server-pyproject.toml', 'pyproject.toml'),
                           (package / 'templates/server-uv.lock', 'uv.lock'),
                           (package / 'templates/server-README.md', 'README.md')]:
        shutil.copyfile(source, server / target)
    (server / 'manifest.json').write_text(dump(plan.manifest))
    (server / 'checks.json').write_bytes(checks_raw)
    (server / '.env.example').write_text('SYNTHETIC_API_TOKEN=synthetic-fixture-token\n')
    (staging / 'tool-plan.json').write_text(dump(plan.manifest))
    (staging / 'coverage.json').write_text(dump(plan.coverage))


def tree_hashes(root):
    return {str(p.relative_to(root)): digest(p.read_bytes()) for p in sorted(root.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.name != 'verification.json'}

"""Public one-shot build flow: snapshot -> propose -> bind -> emit -> verify.

Every run owns a private staging directory. Only a passing generated-artifact
check allows atomic no-replace publication. Failure/cancellation removes that
run's staging tree and never reuses previous verification or changes other runs.
"""
import argparse
import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import tempfile
from .compiler import bind, emit, digest, dump, tree_hashes, NeedsInput
from .design import ReplayPlanner, ResponsesPlanner
from .openapi import catalogue, policy_validate
from .runtime import strict_json
from .verification import verify

BUILD_TIMEOUT = 120
PROPOSAL_TIMEOUT = 45


@dataclass(frozen=True)
class BuildRequest:
    """Paths are case-local; inputs are immutable snapshots for one build."""
    root: Path
    spec: Path
    brief: Path
    policy: Path
    fixtures: Path
    out: Path


def snapshot(path, root, limit):
    path = root / path if not path.is_absolute() else path
    # A resolved containment check alone misses a symlink that stays in-root.
    root = root.resolve()
    if not path.is_relative_to(root / 'fixtures') or any(p.is_symlink() for p in [path, *path.parents] if p.is_relative_to(root)) or not path.is_file():
        raise ValueError('input_path')
    if not path.resolve().is_relative_to(root / 'fixtures'):
        raise ValueError('input_escape')
    with path.open('rb') as handle:
        raw = handle.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('input_limit')
    return raw


def task_ids(brief):
    result = []
    for line in brief.splitlines():
        if not line.strip():
            continue
        key, sep, text = line.partition(':')
        if not sep or not key.strip() or not text.strip() or key.strip() in result:
            raise ValueError('task_brief_format')
        result.append(key.strip())
    if not 1 <= len(result) <= 20:
        raise ValueError('task_count')
    return result


def publish(staging, out):
    # renameatx_np(RENAME_EXCL) provides atomic no-clobber publication on macOS.
    # This case intentionally fails closed on platforms lacking its sandbox.
    import ctypes
    libc = ctypes.CDLL(None, use_errno=True)
    if not hasattr(libc, 'renamex_np'):
        raise ValueError('atomic_publication_unavailable')
    if libc.renamex_np(os.fsencode(staging), os.fsencode(out), 0x00000004) != 0:
        raise OSError(ctypes.get_errno(), 'atomic_publication_failed')


async def build(request, planner):
    staging = None
    stage = 'inputs'
    try:
        async with asyncio.timeout(BUILD_TIMEOUT):
            if request.root.is_symlink():
                raise ValueError('case_root')
            root = request.root.resolve()
            artifacts = root / 'artifacts'
            if artifacts.is_symlink():
                raise ValueError('artifact_symlink')
            artifacts.mkdir(exist_ok=True)
            out = request.out if request.out.is_absolute() else root / request.out
            if out.parent != artifacts or out.is_symlink() or out.exists() or out.name in {'', '.', '..'}:
                raise ValueError('output_conflict_or_escape')
            inputs = {name: snapshot(path, root, cap) for name, path, cap in [
                ('source', request.spec, 1048576), ('brief', request.brief, 8192),
                ('policy', request.policy, 16384), ('checks', request.fixtures, 65536)]}
            document, policy = strict_json(inputs['source']), policy_validate(strict_json(inputs['policy']))
            checks = strict_json(inputs['checks'])
            from .check_server import validate_checks
            validate_checks(checks, policy['destination'])
            brief = inputs['brief'].decode('utf-8')
            tasks = task_ids(brief)
            catalog, coverage = catalogue(document, policy)
            stage = 'proposal'
            async with asyncio.timeout(PROPOSAL_TIMEOUT):
                proposal = await planner.propose(list(catalog.values()), brief)
            if len(dump(proposal).encode()) > 32768:
                raise ValueError('proposal_output_limit')
            hashes = {name: digest(raw) for name, raw in inputs.items()}
            hashes['proposal'] = digest(dump(proposal).encode())
            stage = 'binding'
            plan = bind(catalog, coverage, policy, proposal, tasks, hashes)
            stage = 'emission'
            staging = Path(tempfile.mkdtemp(prefix='.staging-', dir=artifacts))
            emit(plan, staging, inputs['checks'])
            before = tree_hashes(staging)
            stage = 'verification'
            report = await verify(staging)
            if tree_hashes(staging) != before:
                raise ValueError('artifact_changed_during_verification')
            evidence = {'result': 'passed', 'verified_on': datetime.now(timezone.utc).isoformat(),
                        'model': {'mode': planner.mode, 'semantic_evaluation': 'unverified'},
                        'mock_service': report, 'real_service': 'not-run', 'deployment': 'not-run',
                        'files': before, 'input_hashes': hashes,
                        'versions': {'template': '1', 'python': '3.14', 'mcp': '2.3.0', 'protocol': '2026-07-28'}}
            (staging / 'verification.json').write_text(dump(evidence))
            stage = 'publication'
            if artifacts.is_symlink() or not staging.is_dir() or staging.is_symlink() or out.parent.resolve() != artifacts.resolve():
                raise ValueError('publication_path_changed')
            publish(staging, out)
            staging = None
            return {'status': 'verified', 'directory': str(out), 'mode': planner.mode, 'scope': 'synthetic fixture protocol and HTTP adapter only'}
    except asyncio.CancelledError:
        return {'status': 'cancelled', 'stage': stage}
    except TimeoutError:
        return {'status': 'timeout', 'stage': stage}
    except NeedsInput as exc:
        return {'status': 'needs_input', 'stage': stage, 'code': str(exc)}
    except (ValueError, OSError, TypeError, KeyError, UnicodeError) as exc:
        # Provider/HTTP bodies and raw source values are deliberately absent.
        return {'status': 'failed' if stage in {'verification', 'publication', 'emission'} else 'rejected', 'stage': stage, 'code': type(exc).__name__}
    finally:
        if staging is not None:
            shutil.rmtree(staging)


def write_terminal(stream, text):
    try:
        stream.write(text)
        stream.flush()
    except OSError:
        # At CLI help/result boundaries no runtime work remains. A direct
        # failure exit also prevents a second buffered flush changing exit to120.
        os._exit(1)


class Parser(argparse.ArgumentParser):
    def _print_message(self, message, file=None):
        if message:
            import sys
            write_terminal(file or sys.stderr, message)


def main():
    p = Parser(description=__doc__)
    p.add_argument('action', choices=['build'])
    for name, default in [('spec', 'openapi.json'), ('brief', 'tasks.txt'), ('policy', 'policy.json'), ('fixtures', 'checks.json'), ('proposal', 'proposal.json')]:
        p.add_argument('--' + name, type=Path, default=Path('fixtures/customer-invoices') / default)
    p.add_argument('--planner', choices=['replay', 'provider'], default='replay')
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    root = Path.cwd()
    try:
        if args.planner == 'replay':
            planner = ReplayPlanner(snapshot(args.proposal, root, 32768))
        else:
            # Credential lookup occurs only after explicit provider selection.
            token = os.environ.get('OPENAI_API_KEY')
            if not token:
                raise ValueError('provider_credential_unavailable')
            planner = ResponsesPlanner(token)
        result = asyncio.run(build(BuildRequest(root, args.spec, args.brief, args.policy, args.fixtures, args.out), planner))
    except (ValueError, OSError, KeyError, UnicodeError):
        result = {'status': 'rejected', 'stage': 'inputs', 'code': 'planner_input_unavailable'}
    import sys
    write_terminal(sys.stdout, dump(result))
    raise SystemExit(0 if result['status'] == 'verified' else 1)


if __name__ == '__main__':
    main()

"""Exercise an installed Agent 09 CLI from an unrelated working directory."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

executable = str(Path(sys.argv[1]).resolve())
env = dict(os.environ)
env.pop('PYTHONPATH', None)
env.pop('OPENAI_API_KEY', None)
count = 0
with tempfile.TemporaryDirectory(prefix='agent09-cli-') as directory:
    work = Path(directory)
    db = work / 'workflow ?# .sqlite'

    def cli(*args, code=None, success=True, database=None):
        global count
        run = subprocess.run([executable, *args, '--db', str(database or db)], cwd=work,
                             env=env, text=True, capture_output=True, timeout=6)
        count += 1
        assert run.returncode == (0 if success else 2), (args, run.returncode, run.stdout, run.stderr)
        assert not run.stderr, (args, run.stderr)
        value = json.loads(run.stdout)
        if code:
            assert value['code'] == code, (args, value)
        return value

    def submit(identifier, equipment='keyboard', requester='staff-001', profile='success'):
        file = work / (identifier + '.json')
        file.write_text(json.dumps(dict(request_id=identifier, requester_id=requester,
            equipment_code=equipment, quantity=1, justification='Synthetic training request')))
        return cli('submit', str(file), '--command-id', identifier+'-submit', '--profile', profile,
                   code='submitted')

    cli('init', code='initialized')
    cli('init', code='initialized')
    original = submit('routine')
    assert original['request']['total_sen'] == 25000
    cli('advance', 'routine', '--command-id', 'routine-assess', code='ready')
    done = cli('advance', 'routine', '--command-id', 'routine-fulfill', code='fulfilled')
    assert done['request']['attempts'] == 1 and done['request']['fulfillment']
    assert submit('routine') == original
    assert cli('advance', 'routine', '--command-id', 'routine-fulfill') == done
    cli('advance', 'routine', '--command-id', 'routine-noop', code='terminal_noop')
    history = cli('audit', 'routine')['events']
    assert [event['seq'] for event in history] == [1,2,3]

    submit('review', 'laptop')
    cli('advance', 'review', '--command-id', 'review-assess', code='awaiting_review')
    waiting = cli('advance', 'review', '--command-id', 'review-wait', code='awaiting_review')
    common = ['review', 'review', '--decision', 'approve', '--reason', 'Training approval']
    cli(*common, '--reviewer', 'unknown', '--expected-version', '2', '--command-id', 'bad-review',
        code='reviewer_forbidden', success=False)
    cli(*common, '--reviewer', 'ops-reviewer', '--expected-version', '1', '--command-id', 'stale-review',
        code='stale_version', success=False)
    approved_args = common + ['--reviewer', 'ops-reviewer', '--expected-version', '2', '--command-id', 'approved']
    approved = cli(*approved_args, code='ready')
    assert cli('advance', 'review', '--command-id', 'review-wait') == waiting
    cli('advance', 'review', '--command-id', 'review-fulfill', code='fulfilled')
    assert cli(*approved_args) == approved
    assert cli('show', 'review')['request']['version'] == 4

    submit('reject', 'laptop')
    cli('advance', 'reject', '--command-id', 'reject-assess')
    cli('review', 'reject', '--decision', 'reject', '--reviewer', 'finance-reviewer',
        '--reason', 'Training rejection', '--expected-version', '2', '--command-id', 'rejected', code='rejected')
    cli('advance', 'reject', '--command-id', 'reject-next', code='terminal_noop')
    assert cli('show', 'reject')['request']['fulfillment'] is None

    submit('cancel')
    cli('cancel', 'cancel', '--reason', 'Withdrawn', '--command-id', 'cancelled', code='cancelled')
    cli('advance', 'cancel', '--command-id', 'cancel-next', code='terminal_noop')

    submit('retry', profile='transient_once')
    cli('advance', 'retry', '--command-id', 'retry-assess', code='ready')
    first = cli('advance', 'retry', '--command-id', 'retry-first', code='retry_wait')
    time.sleep(max(0, first['request']['next_attempt_at']/1000-time.time())+0.02)
    second = cli('advance', 'retry', '--command-id', 'retry-second', code='fulfilled')
    assert second['request']['attempts'] == 2
    assert cli('advance', 'retry', '--command-id', 'retry-first') == first

    submit('permanent', profile='permanent_failure')
    cli('advance', 'permanent', '--command-id', 'permanent-assess')
    failed = cli('advance', 'permanent', '--command-id', 'permanent-fail', code='failed')
    assert failed['request']['attempts'] == 1

    bad = work/'bad.json'
    bad.write_text('['*2000+']'*2000)
    cli('submit', str(bad), '--command-id', 'bad-input', code='invalid_input', success=False)
    bad.write_text(json.dumps(dict(request_id='bad-unicode', requester_id='staff-001',
        equipment_code='keyboard', quantity=1, justification=chr(0xD800))))
    cli('submit', str(bad), '--command-id', 'bad-unicode', code='invalid_input', success=False)
    cli('advance', 'unknown', '--command-id', 'unknown-advance', code='request_missing', success=False)
    cli('init', database=Path(':memory:'), code='initialized')
    assert (work / ':memory:').is_file()
    cli('show', 'unknown', database=Path(':memory:'), code='request_missing', success=False)
    states = {name: cli('show', name)['request']['state'] for name in
              ('routine','review','reject','cancel','retry','permanent')}
    print(json.dumps({'result':'passed','cli_invocations':count,'scenarios':states,
                      'db_path_special_characters':True,'cwd_outside_case':True}, sort_keys=True))

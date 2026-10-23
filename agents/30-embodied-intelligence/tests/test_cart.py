"""Observable contract checks, with independent trajectory and energy oracles.

The process tests use the installed interpreter's module entry point. They
exercise real argparse and stdout handling, including a pipe with no reader.
"""

from copy import deepcopy
from dataclasses import replace
from importlib.resources import files
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from embodied_intelligence import cli
from embodied_intelligence.schema import CartState, Command, Event, InvalidRequest, parse_request
from embodied_intelligence.simulator import Dispatcher, run


def fixture(name='normal') -> dict:
    return json.loads(files('embodied_intelligence').joinpath('fixtures', name + '.json').read_bytes())


def request(value=None):
    return parse_request(json.dumps(fixture() if value is None else value).encode())


def command(action_id='a', version=0, velocity=1):
    return Command(action_id, version, velocity)


def state(**changes):
    return replace(request().state, **changes)


class DispatcherTests(unittest.TestCase):
    def reject(self, initial, proposal, reason):
        dispatch = Dispatcher(initial)
        before = dispatch.state
        result = dispatch.dispatch(proposal)
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, reason)
        self.assertEqual(dispatch.state, before)
        self.assertEqual(dispatch.effects, ())
        self.assertIsNone(result.receipt)

    def test_integer_trajectory_and_energy_oracle(self):
        dispatch = Dispatcher(state())
        for index, (velocity, position, battery) in enumerate([
            (3, 3, 26), (3, 6, 22), (1, 7, 20), (0, 7, 19),
        ]):
            receipt = dispatch.dispatch(command(str(index), index, velocity)).receipt
            self.assertIsNotNone(receipt)
            self.assertEqual((receipt.after.position, receipt.after.battery), (position, battery))
            self.assertEqual(receipt.after.velocity, velocity)
            self.assertEqual(receipt.after.version, index + 1)
        self.assertEqual(len(dispatch.effects), 4)

    def test_excessive_positive_and_negative_speed(self):
        for velocity in (-100, -4, 4, 100):
            with self.subTest(velocity=velocity):
                self.reject(state(position=50), command(velocity=velocity), 'excessive_speed')

    def test_stale_observation(self):
        self.reject(state(version=5), command(version=4), 'stale_observation')

    def test_both_track_boundaries(self):
        self.reject(state(position=0), command(velocity=-1), 'out_of_bounds')
        self.reject(state(position=100), command(velocity=1), 'out_of_bounds')

    def test_obstacle_crossing_in_both_directions(self):
        self.reject(state(position=0, obstacles=(2,)), command(velocity=3), 'obstacle_crossing')
        self.reject(state(position=4, obstacles=(2,)), command(velocity=-3), 'obstacle_crossing')

    def test_obstacle_endpoints_and_zero_motion(self):
        self.reject(state(position=0, obstacles=(3,)), command(velocity=3), 'obstacle_crossing')
        self.reject(state(position=3, obstacles=(3,)), command(velocity=0), 'obstacle_crossing')
        self.reject(state(position=3, obstacles=(3,)), command(velocity=-1), 'obstacle_crossing')

    def test_insufficient_and_exact_battery(self):
        self.reject(state(battery=3), command(velocity=3), 'insufficient_battery')
        dispatch = Dispatcher(state(battery=4))
        self.assertTrue(dispatch.dispatch(command(velocity=3)).accepted)
        self.assertEqual(dispatch.state.battery, 0)

    def test_zero_motion_still_costs_energy(self):
        self.reject(state(battery=0), command(velocity=0), 'insufficient_battery')
        dispatch = Dispatcher(state(battery=1))
        self.assertEqual(dispatch.dispatch(command(velocity=0)).receipt.energy, 1)
        self.assertEqual(dispatch.state.battery, 0)

    def test_exact_replay_returns_prior_receipt_without_overwriting_new_state(self):
        dispatch = Dispatcher(state())
        original = command()
        first = dispatch.dispatch(original)
        dispatch.dispatch(command('b', 1, 2))
        current = dispatch.state
        replay = dispatch.dispatch(original)
        self.assertTrue(replay.replayed)
        self.assertIs(replay.receipt, first.receipt)
        self.assertEqual(dispatch.state, current)
        self.assertEqual(len(dispatch.effects), 2)

    def test_changed_action_id_fields_are_rejected(self):
        for changed in (command(version=1), command(velocity=2)):
            dispatch = Dispatcher(state())
            dispatch.dispatch(command())
            current = dispatch.state
            effects = dispatch.effects
            result = dispatch.dispatch(changed)
            self.assertEqual(result.reason, 'changed_action_id')
            self.assertEqual(dispatch.state, current)
            self.assertEqual(dispatch.effects, effects)

    def test_rejected_id_can_be_corrected(self):
        dispatch = Dispatcher(state())
        self.assertFalse(dispatch.dispatch(command(velocity=4)).accepted)
        self.assertTrue(dispatch.dispatch(command(velocity=2)).accepted)
        self.assertEqual(len(dispatch.effects), 1)

    def test_world_update_invalidates_old_command(self):
        dispatch = Dispatcher(state())
        dispatch.update_obstacles(Event(0, 'obstacles', (80,)))
        current = dispatch.state
        self.assertEqual(dispatch.dispatch(command()).reason, 'stale_observation')
        self.assertEqual(dispatch.state, current)
        self.assertEqual(current.version, 1)
        self.assertEqual(len(dispatch.effects), 1)

    def test_emergency_precedes_replay_and_cannot_restart(self):
        dispatch = Dispatcher(state())
        original = command()
        dispatch.dispatch(original)
        dispatch.emergency_stop()
        frozen = dispatch.state
        effects = dispatch.effects
        for proposal in (original, command('new', frozen.version, 1)):
            self.assertEqual(dispatch.dispatch(proposal).reason, 'emergency_stop')
        dispatch.update_obstacles(Event(1, 'obstacles', (5,)))
        dispatch.emergency_stop()
        self.assertEqual(dispatch.state, frozen)
        self.assertEqual(dispatch.effects, effects)
        self.assertEqual((frozen.position, frozen.velocity, frozen.battery, frozen.version), (1, 0, 28, 2))

    def test_grid_oracle_checks_whole_segment_and_conservation(self):
        # Enumerating integer points independently checks the interval guard.
        for position in range(4, 8):
            for velocity in range(-3, 4):
                for obstacle in range(2, 11):
                    if obstacle == position:
                        continue
                    with self.subTest(position=position, velocity=velocity, obstacle=obstacle):
                        initial = state(position=position, obstacles=(obstacle,))
                        dispatch = Dispatcher(initial)
                        result = dispatch.dispatch(command(velocity=velocity))
                        direction = 1 if velocity >= 0 else -1
                        visited = list(range(position, position + velocity + direction, direction))
                        blocked = obstacle in visited
                        self.assertEqual(result.accepted, not blocked)
                        if blocked:
                            self.assertEqual(dispatch.state, initial)
                        else:
                            self.assertEqual(dispatch.state.position, position + velocity)
                            self.assertEqual(dispatch.state.battery, 29 - abs(velocity))
                            self.assertEqual(dispatch.state.version, 1)


class RunTests(unittest.TestCase):
    def test_normal_report_matches_independent_expected_trace(self):
        report = run(request())
        self.assertEqual((report['outcome'], report['ticks'], report['replans']), ('complete', 4, 0))
        self.assertEqual([effect['after']['position'] for effect in report['effects']], [3, 6, 7, 7])
        self.assertEqual([effect['energy'] for effect in report['effects']], [4, 4, 2, 1])
        self.assertEqual(report['final_state'], dict(position=7, velocity=0, battery=19,
                                                    obstacles=(20,), version=4, emergency_stop=False))

    def test_replan_discards_invalid_plan_tail(self):
        value = fixture('replan')
        value['plans'][0].append(dict(action_id='must-not-run', expected_version=0, velocity=1))
        report = run(request(value))
        self.assertEqual((report['outcome'], report['replans'], report['ticks']), ('complete', 1, 5))
        self.assertNotIn('must-not-run', [item['command']['action_id'] for item in report['attempts']])
        self.assertEqual(len(report['effects']), 4)

    def test_replacement_exhaustion_is_replan_limit(self):
        value = fixture()
        value['plans'] = [[], []]
        report = run(request(value))
        self.assertEqual((report['outcome'], report['reason'], report['replans']), ('limit', 'replan_limit', 1))
        self.assertEqual(report['effects'], [])

    def test_second_rejected_plan_is_limit(self):
        value = fixture('replan')
        value['plans'][1] = [dict(action_id='also-fast', expected_version=0, velocity=-4)]
        report = run(request(value))
        self.assertEqual((report['outcome'], report['reason'], report['ticks']), ('limit', 'replan_limit', 2))
        self.assertEqual(report['final_state'], report['initial_state'])

    def test_no_replacement_faults_and_explicitly_brakes(self):
        value = fixture()
        value['plans'] = [value['plans'][0][:1]]
        report = run(request(value))
        self.assertEqual((report['outcome'], report['reason']), ('fault', 'plan_exhausted'))
        self.assertEqual([effect['kind'] for effect in report['effects']], ['command', 'brake'])
        self.assertEqual(report['effects'][-1]['energy'], 0)
        self.assertEqual((report['final_state']['position'], report['final_state']['velocity'],
                          report['final_state']['battery'], report['final_state']['version']), (3, 0, 26, 2))

    def test_twenty_tick_limit(self):
        report = run(request(fixture('tick-limit')))
        self.assertEqual((report['outcome'], report['reason'], report['ticks']), ('limit', 'tick_limit', 20))
        self.assertEqual((len(report['effects']), report['final_state']['battery'],
                          report['final_state']['version']), (20, 10, 20))

    def test_replays_count_toward_tick_limit_without_second_effect(self):
        value = fixture()
        original = value['plans'][0][0]
        value['plans'] = [[original, deepcopy(original), deepcopy(original)]]
        value['max_ticks'] = 3
        report = run(request(value))
        self.assertEqual((report['reason'], report['ticks']), ('tick_limit', 3))
        self.assertEqual([effect['kind'] for effect in report['effects']], ['command', 'brake'])
        self.assertEqual([item['replayed'] for item in report['attempts']], [False, True, True])

    def test_final_allowed_command_can_complete(self):
        value = fixture()
        value['max_ticks'] = 4
        self.assertEqual(run(request(value))['outcome'], 'complete')

    def test_emergency_before_obstacles_and_pending_command(self):
        report = run(request(fixture('emergency')))
        self.assertEqual((report['outcome'], report['ticks']), ('halted', 1))
        self.assertEqual([effect['kind'] for effect in report['effects']], ['command', 'emergency_stop'])
        self.assertEqual(report['unprocessed_events'], 1)
        self.assertEqual((report['final_state']['position'], report['final_state']['battery'],
                          report['final_state']['version'], report['final_state']['velocity']), (3, 26, 2, 0))

    def test_emergency_before_success_and_before_replayed_command(self):
        value = fixture('replay')
        value['events'] = [dict(tick=1, kind='emergency_stop')]
        report = run(request(value))
        self.assertEqual(report['ticks'], 1)
        self.assertEqual(len(report['attempts']), 1)
        value['state']['position'] = value['goal']
        value['events'] = [dict(tick=0, kind='emergency_stop')]
        self.assertEqual(run(request(value))['outcome'], 'halted')

    def test_emergency_at_tick_limit_boundary(self):
        value = fixture()
        value['max_ticks'] = 1
        value['events'] = [dict(tick=1, kind='emergency_stop')]
        report = run(request(value))
        self.assertEqual((report['outcome'], report['reason']), ('halted', 'emergency_stop'))

    def test_initial_latched_emergency_has_no_new_effect(self):
        value = fixture()
        value['state']['emergency_stop'] = True
        report = run(request(value))
        self.assertEqual((report['outcome'], report['ticks'], report['effects']), ('halted', 0, []))

    def test_obstacle_world_event_stales_plan_before_dispatch(self):
        value = fixture()
        value['events'] = [dict(tick=0, kind='obstacles', obstacles=[2])]
        report = run(request(value))
        self.assertEqual(report['reason'], 'stale_observation')
        self.assertEqual([effect['kind'] for effect in report['effects']], ['obstacles'])
        self.assertEqual(report['final_state']['position'], 0)

    def test_isolated_runs_have_no_receipt_or_state_leak(self):
        self.assertEqual(run(request()), run(request()))

    def test_rejected_command_followed_by_terminal_brake_is_separately_traced(self):
        value = fixture()
        value['plans'][0][1]['expected_version'] = 0
        report = run(request(value))
        self.assertEqual(report['reason'], 'stale_observation')
        self.assertEqual([effect['kind'] for effect in report['effects']], ['command', 'brake'])
        self.assertEqual(report['attempts'][1]['receipt'], None)
        self.assertEqual(report['effects'][1]['before'], report['effects'][0]['after'])


class ParsingTests(unittest.TestCase):
    def invalid(self, value):
        with self.assertRaises(InvalidRequest):
            request(value)

    def test_unknown_missing_fields_and_boolean_integers(self):
        for path in ('state', 'request', 'command'):
            value = fixture()
            target = value['state'] if path == 'state' else value['plans'][0][0] if path == 'command' else value
            target['extra'] = 'secret'
            self.invalid(value)
        value = fixture()
        del value['max_ticks']
        self.invalid(value)
        for field in ('position', 'velocity', 'battery', 'version'):
            value = fixture()
            value['state'][field] = True
            self.invalid(value)

    def test_duplicate_keys_floats_nonfinite_utf8_and_deep_json(self):
        for raw in (b'{"state":0,"state":1}', b'{"x":1.0}', b'{"x":NaN}', b'{"x":Infinity}',
                    b'\xff', b'[' * 13 + b']' * 13, b'{}' + b' ' * 32768):
            with self.subTest(raw=raw[:30]), self.assertRaises(InvalidRequest):
                parse_request(raw)

    def test_whole_replacement_validated_before_simulation(self):
        value = fixture()
        value['plans'].append([dict(action_id='bad', expected_version=0, velocity='secret')])
        self.invalid(value)

    def test_field_bounds_and_action_identifiers(self):
        for field, invalid in [('position', -1), ('position', 101), ('velocity', 4), ('battery', 101),
                               ('battery', -1), ('version', 1001), ('emergency_stop', 1)]:
            value = fixture()
            value['state'][field] = invalid
            self.invalid(value)
        for action_id in ('', 'x' * 33, 'a b', '💥', '\ud800', 1):
            value = fixture()
            value['plans'][0][0]['action_id'] = action_id
            self.invalid(value)
        for velocity in (-101, 101, True):
            value = fixture()
            value['plans'][0][0]['velocity'] = velocity
            self.invalid(value)

    def test_obstacle_order_duplicates_occupancy_and_emergency_velocity(self):
        for obstacles in ([20, 10], [20, 20], [0], [101], [True]):
            value = fixture()
            value['state']['obstacles'] = obstacles
            self.invalid(value)
        value = fixture()
        value['state'].update(emergency_stop=True, velocity=1)
        self.invalid(value)

    def test_plan_tick_event_limits(self):
        for plans in ([], [[], [], []], [[dict(action_id='a', expected_version=0, velocity=0)] * 21]):
            value = fixture()
            value['plans'] = plans
            self.invalid(value)
        for ticks in (0, 21, True):
            value = fixture()
            value['max_ticks'] = ticks
            self.invalid(value)
        for events in ([dict(tick=20, kind='emergency_stop')],
                       [dict(tick=2, kind='emergency_stop'), dict(tick=1, kind='emergency_stop')],
                       [dict(tick=0, kind='emergency_stop')] * 2,
                       [dict(tick=0, kind='restart')]):
            value = fixture()
            value['events'] = events
            self.invalid(value)

    def test_large_value_tree_and_malformed_syntax(self):
        for raw in (json.dumps([0] * 2049).encode(), b'{', b'null', b'[]', b'{}\n{}'):
            with self.assertRaises(InvalidRequest):
                parse_request(raw)


class CliTests(unittest.TestCase):
    def invoke(self, *args):
        return subprocess.run([sys.executable, '-m', 'embodied_intelligence', *args],
                              capture_output=True, timeout=10)

    def test_real_cli_normal_and_fixture_outcomes(self):
        for name, code, outcome in [('normal', 0, 'complete'), ('replan', 0, 'complete'),
                                     ('emergency', 0, 'halted'), ('obstacle', 1, 'fault'),
                                     ('replay', 0, 'complete'), ('tick-limit', 1, 'limit')]:
            with self.subTest(name=name):
                result = self.invoke('--fixture', name)
                self.assertEqual(result.returncode, code, result.stderr)
                self.assertEqual(json.loads(result.stdout)['outcome'], outcome)
                self.assertEqual(result.stderr, b'')
                self.assertLess(len(result.stdout), 65536)

    def test_invalid_arguments_are_bounded_and_sanitized(self):
        secret = 'DO_NOT_PRINT_' + 'x' * 5000
        for args in [('--unknown', secret), ('--fixture', secret), ('--fixture',),
                     ('--input', 'x', '--fixture', 'normal'), ('--fi', 'normal')]:
            result = self.invoke(*args)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(json.loads(result.stdout), {'outcome': 'invalid-input', 'error': 'invalid_arguments'})
            self.assertEqual(result.stderr, b'')
            self.assertLess(len(result.stdout), 100)

    def test_local_file_normal_and_bounded_invalid_data(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'private.json'
            path.write_text(json.dumps(fixture()))
            self.assertEqual(self.invoke('--input', str(path)).returncode, 0)
            for data in (b'{SECRET', b'x' * 32769, b'\xff'):
                path.write_bytes(data)
                result = self.invoke('--input', str(path))
                self.assertEqual((result.returncode, json.loads(result.stdout)),
                                 (2, {'outcome': 'invalid-input', 'error': 'invalid_request'}))
                self.assertEqual(result.stderr, b'')

    def test_special_files_final_symlink_and_missing_file_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            target = folder / 'valid.json'
            target.write_text(json.dumps(fixture()))
            link = folder / 'link'
            link.symlink_to(target)
            fifo = folder / 'fifo'
            os.mkfifo(fifo)
            for path in (link, fifo, folder, folder / 'SECRET-missing'):
                result = self.invoke('--input', str(path))
                self.assertEqual((result.returncode, json.loads(result.stdout)),
                                 (2, {'outcome': 'invalid-input', 'error': 'input_unavailable'}))
                self.assertEqual(result.stderr, b'')

    def test_help_has_real_entry_point(self):
        result = self.invoke('--help')
        self.assertEqual(result.returncode, 0)
        self.assertIn(b'embodied-cart', result.stdout)
        self.assertEqual(result.stderr, b'')

    def test_closed_stdout_is_quiet_buffered_and_unbuffered(self):
        for unbuffered in (False, True):
            for args in ([], ['--help'], ['--unknown', 'SECRET']):
                with self.subTest(unbuffered=unbuffered, args=args):
                    read_end, write_end = os.pipe()
                    os.close(read_end)
                    invocation = [sys.executable] + (['-u'] if unbuffered else [])
                    try:
                        process = subprocess.Popen([*invocation, '-m', 'embodied_intelligence', *args],
                                                   stdout=write_end, stderr=subprocess.PIPE)
                    finally:
                        os.close(write_end)
                    _, stderr = process.communicate(timeout=10)
                    self.assertEqual(process.returncode, 0, stderr)
                    self.assertEqual(stderr, b'')

    def test_keyboard_interrupt_reports_cancelled(self):
        from io import StringIO
        output = StringIO()
        with patch.object(cli, 'run', side_effect=KeyboardInterrupt), patch.object(sys, 'stdout', output):
            code = cli.main([])
        self.assertEqual(code, 130)
        self.assertEqual(json.loads(output.getvalue()), {'outcome': 'cancelled', 'reason': 'interrupted'})


if __name__ == '__main__':
    unittest.main()

"""Behavior checks use independent rational arithmetic and explicit policy cases."""

from copy import deepcopy
from fractions import Fraction
from importlib.resources import files
import json
import unittest

from education_intelligence.core import BKTParameters, InvalidInput, parse_request, run, update_mastery


def fixture():
    return json.loads(files("education_intelligence").joinpath("fixtures/session.json").read_text())


def execute(data):
    return run(parse_request(json.dumps(data).encode())).record()


class LearningTests(unittest.TestCase):
    def assert_invalid(self, data, code=None):
        with self.assertRaises(InvalidInput) as caught:
            execute(data)
        if code:
            self.assertEqual(caught.exception.code, code)

    def test_correct_observation_then_transition_independent_fraction(self):
        result = execute(fixture())
        # Rational odds derive the observation independently of the implementation.
        odds = Fraction(7, 3) * Fraction(9, 2)
        posterior = odds / (1 + odds)
        learned = posterior + (1 - posterior) / 10
        self.assertAlmostEqual(result['trace'][0]['posterior'], float(posterior))
        self.assertAlmostEqual(result['state'][1]['mastery'], float(learned))
        self.assertEqual(result['eligible'], ['add', 'count'])
        self.assertEqual(result['practice'], ['add'])
        self.assertEqual(result['next_activity'], {'kind':'review','objective':'count',
                          'prompt':'How many stones are in [stone, stone, stone]?'})
        self.assertEqual(result['due_reviews'], [{'objective':'count','due_at':'2026-10-22T12:00:00Z'}])

    def test_incorrect_fraction_and_transition_order(self):
        odds = Fraction(1, 4) * Fraction(1, 8)
        posterior = odds / (1 + odds)
        expected = posterior + (1 - posterior) / 10
        observed, learned = update_mastery(.2, False, BKTParameters(.2, .1, .1))
        self.assertAlmostEqual(observed, float(posterior))
        self.assertAlmostEqual(learned, float(expected))

    def test_missing_preserves_entire_state(self):
        data = fixture()
        data['answers'][0]['answer'] = None
        result = execute(data)
        self.assertEqual(result['state'], sorted(data['state'], key=lambda r:r['objective']))
        self.assertEqual(result['status'], 'evidence_required')
        self.assertIsNone(result['trace'][0]['posterior'])

    def test_one_cold_correct_does_not_meet_threshold(self):
        data = fixture()
        data['state'][0]['mastery'] = .2
        result = execute(data)
        self.assertAlmostEqual(result['trace'][0]['mastery'], 0.5764705882352941)
        self.assertEqual(result['eligible'], ['count'])
        self.assertEqual(result['status'], 'practice_required')

    def test_uniform_inclusive_threshold(self):
        data = fixture()
        data['answers'] = []
        data['state'][0]['mastery'] = .8
        result = execute(data)
        self.assertEqual(result['eligible'], ['add', 'count'])
        self.assertEqual(result['practice'], ['add'])
        data['state'][0]['mastery'] = .799999999
        self.assertEqual(execute(data)['eligible'], ['count'])

    def test_session_unlocks_practice_in_evidence_order(self):
        data = fixture()
        data['answers'] += [
            {'objective':'add','answer':'5','observed_at':'2026-10-16T12:00:00Z'},
            {'objective':'add','answer':'5','observed_at':'2026-10-17T12:00:00Z'},
            {'objective':'multiply','answer':'6','observed_at':'2026-10-18T12:00:00Z'}]
        result = execute(data)
        self.assertEqual([r['objective'] for r in result['trace']], ['count','add','add','multiply'])
        self.assertEqual(result['eligible'], ['add','count','multiply'])
        self.assertEqual(result['practice'], ['multiply'])

    def test_ineligible_answer_rejects_whole_run(self):
        data = fixture()
        data['answers'].append({'objective':'multiply','answer':'6','observed_at':'2026-10-16T12:00:00Z'})
        before = deepcopy(data)
        self.assert_invalid(data, 'ineligible_objective')
        self.assertEqual(data, before)

    def test_hint_progression_and_stop(self):
        data = fixture()
        data['answers'] = [{'objective':'count','answer':'wrong','observed_at':f'2026-10-{day:02d}T12:00:00Z'} for day in range(15,19)]
        result = execute(data)
        self.assertEqual([r['hint_level'] for r in result['trace']], [1,2,3])
        self.assertEqual(len({r['hint'] for r in result['trace']}), 3)
        self.assertEqual(result['status'], 'teacher_review')
        self.assertEqual(result['unprocessed_answers'], 1)
        self.assertIsNone(result['next_activity'])
        self.assertEqual(next(r for r in result['state'] if r['objective']=='count')['attempts'], 3)

    def test_correct_resets_hint_and_failure(self):
        data = fixture()
        data['answers'] = [{'objective':'count','answer':'wrong','observed_at':'2026-10-15T12:00:00Z'},
                           {'objective':'count','answer':'3','observed_at':'2026-10-16T12:00:00Z'}]
        result = execute(data)
        self.assertEqual([r['hint_level'] for r in result['trace']], [1,0])
        self.assertIsNone(result['trace'][1]['hint'])

    def test_existing_teacher_review_processes_nothing(self):
        data = fixture()
        item = data['state'][0]
        item.update(attempts=3,failures=3,last_evidence='2026-10-14T12:00:00Z',due_at='2026-10-15T12:00:00Z')
        result = execute(data)
        self.assertEqual(result['status'], 'teacher_review')
        self.assertEqual(result['trace'], [])
        self.assertEqual(result['unprocessed_answers'], 1)

    def test_due_boundary_uses_clock_and_evidence_time(self):
        data = fixture()
        data['now'] = '2026-10-22T11:59:59Z'
        self.assertEqual(execute(data)['due_reviews'], [])
        data['now'] = '2026-10-22T12:00:00Z'
        self.assertEqual(execute(data)['due_reviews'][0]['objective'], 'count')

    def test_due_order_and_prerequisite_filter(self):
        data = fixture()
        data['answers'] = []
        for item in data['state']:
            item.update(mastery=.8,attempts=1,last_evidence='2026-10-01T00:00:00Z',due_at='2026-10-02T00:00:00Z')
        result = execute(data)
        self.assertEqual([r['objective'] for r in result['due_reviews']], ['add','count','multiply'])
        self.assertEqual(result['status'], 'completed')
        data['state'][0]['mastery'] = .2
        self.assertNotIn('add', [r['objective'] for r in execute(data)['due_reviews']])

    def test_replay_and_explicit_state_roundtrip(self):
        data = fixture()
        first = execute(data)
        data['state'] = first['state']
        self.assert_invalid(data, 'replayed_evidence')
        data['answers'] = []
        self.assertEqual(execute(data)['state'], first['state'])

    def test_cycles_duplicates_unknown_nodes_and_dependencies(self):
        for mode in ('cycle','self','duplicate','unknown','missing_parent','duplicate_parent'):
            with self.subTest(mode=mode):
                data = fixture()
                if mode == 'cycle': data['graph'][0]['prerequisites'] = ['multiply']
                if mode == 'self': data['graph'][0]['prerequisites'] = ['count']
                if mode == 'duplicate': data['graph'][1]['objective'] = 'count'
                if mode == 'unknown': data['graph'][0]['objective'] = 'secret'
                if mode == 'missing_parent': data['graph'] = data['graph'][:2]; data['graph'][0]['prerequisites'] = ['multiply']
                if mode == 'duplicate_parent': data['graph'][2]['prerequisites'] = ['add','add']
                self.assert_invalid(data, 'invalid_graph')

    def test_probability_rejects_invalid_values(self):
        for name in ('guess','slip','learn'):
            for value in (-.1,1.1,True,'0.2',None,1e300):
                with self.subTest(name=name,value=value):
                    data = fixture(); data['parameters'][name] = value
                    self.assert_invalid(data, 'invalid_probability')

    def test_zero_denominator_correct_and_incorrect(self):
        for correct, prior, guess, slip in ((True,0,0,0),(False,1,0,0),(True,1,0,1),(False,0,1,0)):
            with self.subTest(correct=correct,prior=prior):
                data = fixture()
                data['state'][0]['mastery'] = prior
                data['parameters'].update(guess=guess,slip=slip)
                data['answers'][0]['answer'] = '3' if correct else 'wrong'
                self.assert_invalid(data, 'impossible_observation')

    def test_probability_endpoints_are_supported_when_possible(self):
        self.assertEqual(update_mastery(0, True, BKTParameters(1,1,1)), (0,1))
        self.assertEqual(update_mastery(1, False, BKTParameters(0,1,0)), (1,1))

    def test_invalid_time_future_and_order(self):
        for value in ('2026-02-30T00:00:00Z','2026-10-24T00:00:00Z','2026-10-15T00:00:60Z',
                      '2026-10-15T00:00:00+00:00','1999-01-01T00:00:00Z','2026-10-15T00:00:00.1Z'):
            with self.subTest(value=value):
                data=fixture(); data['answers'][0]['observed_at']=value
                self.assert_invalid(data, 'invalid_time')
        data=fixture(); data['answers'].append({**data['answers'][0],'observed_at':'2026-10-14T00:00:00Z'})
        self.assert_invalid(data,'invalid_time')

    def test_state_completeness_and_counters(self):
        changes = ({'attempts':True},{'failures':1},{'attempts':-1},{'mastery':2},
                   {'attempts':1},{'due_at':'2026-10-15T00:00:00Z'},
                   {'attempts':1,'last_evidence':'2026-10-24T00:00:00Z','due_at':'2026-10-25T00:00:00Z'},
                   {'attempts':1,'last_evidence':'2026-10-15T00:00:00Z','due_at':'2026-10-15T00:00:00Z'})
        for change in changes:
            with self.subTest(change=change):
                data=fixture(); data['state'][0].update(change); self.assert_invalid(data)
        data=fixture(); data['state'].pop(); self.assert_invalid(data)
        data=fixture(); data['state'][1]=deepcopy(data['state'][0]); self.assert_invalid(data)

    def test_attempt_and_answer_bounds(self):
        data=fixture(); data['state'][0].update(attempts=10000,last_evidence='2026-10-14T00:00:00Z',due_at='2026-10-15T00:00:00Z')
        self.assert_invalid(data,'bound_exceeded')
        data=fixture(); data['answers']*=13; self.assert_invalid(data,'bound_exceeded')
        data=fixture(); data['answers'][0]['answer']='x'*129; self.assert_invalid(data,'bound_exceeded')

    def test_schema_unknown_fields_types_and_duplicate_keys(self):
        for raw in (b'{"now":0,"now":1}',b'[]',b'NaN',b'{"p":1e400}',b'\xff',b'{'):
            with self.subTest(raw=raw), self.assertRaises(InvalidInput): parse_request(raw)
        data=fixture(); data['unauthorized']='execute'; self.assert_invalid(data,'invalid_schema')
        data=fixture(); data['answers'][0]['answer']=3; self.assert_invalid(data,'invalid_schema')
        data=fixture(); del data['parameters']['slip']; self.assert_invalid(data,'invalid_schema')

    def test_input_and_nesting_bounds(self):
        for raw in (b' '*32769,b'['*20+b'0'+b']'*20):
            with self.assertRaises(InvalidInput) as caught: parse_request(raw)
            self.assertEqual(caught.exception.code,'bound_exceeded')

    def test_answer_is_data_never_code_and_not_echoed(self):
        data=fixture(); data['answers'][0]['answer']='__import__("os").system("exit 99")'
        result=execute(data)
        self.assertEqual(result['trace'][0]['assessment'],'incorrect')
        self.assertNotIn('__import__',json.dumps(result))

    def test_no_cross_run_mutation(self):
        data=fixture(); before=deepcopy(data)
        session=parse_request(json.dumps(data).encode())
        self.assertEqual(run(session).record(),run(session).record())
        self.assertEqual(data,before)

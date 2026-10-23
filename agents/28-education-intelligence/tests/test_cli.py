"""Actual subprocess checks cover the CLI and pipe shutdown, beyond unit mocks."""

from contextlib import redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from education_intelligence import cli


class CliTests(unittest.TestCase):
    def invoke(self, *arguments, **options):
        return subprocess.run([sys.executable,'-m','education_intelligence',*arguments],capture_output=True,timeout=10,**options)

    def test_packaged_fixture_real_process(self):
        result=self.invoke()
        self.assertEqual(result.returncode,0,result.stderr)
        report=json.loads(result.stdout)
        self.assertEqual(report['eligible'],['add','count'])
        self.assertEqual(report['next_activity']['kind'],'review')
        self.assertEqual(result.stderr,b'')

    def test_help_and_invalid_arguments_are_bounded_and_sanitized(self):
        self.assertEqual(self.invoke('--help').stdout.decode(),cli.HELP)
        for arguments in (('SECRET-CALLER-TEXT',),('--input',),('--help','SECRET-CALLER-TEXT'),('--input','--help'),('--bad=SECRET',)):
            with self.subTest(arguments=arguments):
                result=self.invoke(*arguments)
                self.assertEqual(result.returncode,2)
                self.assertEqual(json.loads(result.stdout),{'status':'invalid_input','error':'invalid_arguments'})
                self.assertEqual(result.stderr,b'')
                self.assertLess(len(result.stdout),100)

    def test_closed_stdout_result_help_and_error_buffered_and_unbuffered(self):
        for unbuffered in (False,True):
            for arguments in ([],['--help'],['SECRET']):
                with self.subTest(unbuffered=unbuffered,arguments=arguments):
                    reader, writer=os.pipe()
                    os.close(reader)
                    env={**os.environ,'PYTHONUNBUFFERED':'1' if unbuffered else '0'}
                    try:
                        result=subprocess.run([sys.executable,'-m','education_intelligence',*arguments],
                                              stdout=writer,stderr=subprocess.PIPE,env=env,timeout=10)
                    finally:
                        os.close(writer)
                    self.assertEqual(result.returncode,0,result.stderr)
                    self.assertEqual(result.stderr,b'')

    def test_read_only_stdout_retains_documented_io_failure(self):
        for unbuffered in (False, True):
            for arguments in (['--help'], ['--bad']):
                descriptor = os.open(os.devnull, os.O_RDONLY)
                environment = {**os.environ, 'PYTHONUNBUFFERED': '1' if unbuffered else '0'}
                try:
                    result = subprocess.run([sys.executable, '-m', 'education_intelligence', *arguments],
                                            stdin=subprocess.DEVNULL, stdout=descriptor,
                                            stderr=subprocess.PIPE, env=environment, timeout=5)
                finally:
                    os.close(descriptor)
                with self.subTest(unbuffered=unbuffered, arguments=arguments):
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertEqual(result.stderr, b'')

    def test_input_file_success_and_missing_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'session.json'
            source=cli.files('education_intelligence').joinpath('fixtures/missing.json').read_bytes()
            path.write_bytes(source)
            result=self.invoke('--input',str(path))
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout)['status'],'evidence_required')

    def test_special_files_unavailable_and_input_limits(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            regular=root/'file.json'; regular.write_text('{}')
            link=root/'link'; link.symlink_to(regular)
            fifo=root/'fifo'; os.mkfifo(fifo)
            for path in (root,link,fifo,root/'SECRET-MISSING'):
                with self.subTest(path=path.name):
                    result=self.invoke('--input',str(path))
                    self.assertEqual(result.returncode,2)
                    self.assertEqual(json.loads(result.stdout),{'status':'invalid_input','error':'input_unavailable'})
                    self.assertEqual(result.stderr,b'')
            regular.write_bytes(b'x'*32769)
            self.assertEqual(json.loads(self.invoke('--input',str(regular)).stdout)['error'],'bound_exceeded')
            regular.write_bytes(b'{"SECRET":"raw", "SECRET":"duplicate"}')
            result=self.invoke('--input',str(regular))
            self.assertEqual(json.loads(result.stdout)['error'],'invalid_json')
            self.assertNotIn(b'SECRET',result.stdout)
            regular.write_bytes(b'['*20+b'0'+b']'*20)
            self.assertEqual(json.loads(self.invoke('--input',str(regular)).stdout),
                             {'status':'invalid_input','error':'bound_exceeded'})
            data=json.loads(cli.files('education_intelligence').joinpath('fixtures/session.json').read_text())
            data['state'][0]['mastery']=0
            data['parameters']['guess']=0
            regular.write_text(json.dumps(data))
            result=self.invoke('--input',str(regular))
            self.assertEqual(result.returncode,2)
            self.assertEqual(json.loads(result.stdout),{'status':'invalid_input','error':'impossible_observation'})
            self.assertEqual(result.stderr,b'')

    def test_cancellation_has_no_state(self):
        stream=StringIO()
        with patch.object(sys,'argv',['education-demo']), patch.object(cli,'parse_request',side_effect=KeyboardInterrupt),redirect_stdout(stream):
            self.assertEqual(cli.main(),130)
        self.assertEqual(json.loads(stream.getvalue()),{'status':'cancelled'})

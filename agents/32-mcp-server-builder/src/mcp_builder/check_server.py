"""Fixed standalone acceptance gate: real MCP subprocess + synthetic HTTP.

Expectations are declarative data, distinct from the generated operation table.
macOS sandbox-exec restricts the generated process to the fixture port; a second
live listener proves denied egress. This is network isolation, not a filesystem
sandbox. Temporary cwd, explicit environment and fixed code limit other effects.
"""
import argparse
import asyncio
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from mcp.client import Client
import anyio
from mcp import types
from mcp.shared.message import SessionMessage
from pydantic import TypeAdapter
from jsonschema import Draft202012Validator, SchemaError

MESSAGE_ADAPTER = TypeAdapter(types.JSONRPCMessage)

VERSION = '2026-07-28'
META = {'io.modelcontextprotocol/protocolVersion': VERSION, 'io.modelcontextprotocol/clientCapabilities': {}}
CAP = 256 * 1024


def validate_checks(data, destination):
    """Fixtures can describe calls/results, never commands or test source."""
    if not isinstance(data, dict) or set(data) != {'destination', 'cases', 'tool_schemas'} or data['destination'] != destination:
        raise ValueError('fixture_fields')
    parsed = urlsplit(destination)
    if parsed.scheme != 'http' or parsed.hostname != '127.0.0.1' or not parsed.port:
        raise ValueError('fixture_destination')
    if not isinstance(data['cases'], list) or not 1 <= len(data['cases']) <= 12:
        raise ValueError('fixture_count')
    names = set()
    for c in data['cases']:
        if set(c) != {'tool', 'arguments', 'path', 'bearer', 'result'} or not isinstance(c['arguments'], dict) or not isinstance(c['bearer'], bool) or not isinstance(c['tool'], str) or not isinstance(c['path'], str):
            raise ValueError('fixture_case')
        if not c['path'].startswith(parsed.path + '/') or c['path'].startswith('//') or any(x in c['path'] for x in ['#', '\\', '\r', '\n']):
            raise ValueError('fixture_path')
        names.add(c['tool'])
    if not 1 <= len(names) <= 3:
        raise ValueError('fixture_tool_count')
    expected = data['tool_schemas']
    if not isinstance(expected, dict) or set(expected) != names:
        raise ValueError('fixture_tool_schemas')
    for schemas in expected.values():
        if not isinstance(schemas, dict) or set(schemas) != {'input_schema', 'output_schema'}:
            raise ValueError('fixture_tool_schemas')
        for schema in schemas.values():
            if not isinstance(schema, dict):
                raise ValueError('fixture_tool_schema')
            try:
                Draft202012Validator.check_schema(schema)
            except SchemaError:
                raise ValueError('fixture_tool_schema') from None
    return data


def environment():
    return {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'PYTHONUNBUFFERED': '1', 'PYTHONDONTWRITEBYTECODE': '1', 'SYNTHETIC_API_TOKEN': 'synthetic-fixture-token'}


class Fixture:
    """One bounded local service, owned and stopped by the verifier process."""
    def __init__(self, checks):
        self.checks, self.calls, self.mode = checks, [], 'normal'
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                owner.calls.append({'path': self.path, 'authorization': self.headers.get('Authorization')})
                case = next((c for c in checks['cases'] if c['path'] == self.path), None)
                mode = owner.mode
                code, body, extra = 200, json.dumps(case['result'] if case else {'id': 'encoding'}).encode(), {}
                if mode.startswith('status_'):
                    code, body = int(mode[7:]), b'PRIVATE_UPSTREAM_BODY synthetic-fixture-token'
                elif mode == 'redirect':
                    code, body, extra = 302, b'PRIVATE_UPSTREAM_BODY', {'Location': 'http://127.0.0.1:1/leak'}
                elif mode == 'json':
                    body = b'PRIVATE_UPSTREAM_BODY'
                elif mode == 'schema':
                    body = b'{"unexpected":"PRIVATE_UPSTREAM_BODY"}'
                elif mode == 'encoding':
                    import gzip
                    body = gzip.compress(b'x' * (CAP * 4))
                    extra['Content-Encoding'] = 'gzip'
                elif mode == 'oversize':
                    body = b'"' + b'x' * (CAP + 1) + b'"'
                elif mode in {'slow', 'cancel', 'concurrent'}:
                    time.sleep(5.5 if mode == 'slow' else .8)
                self.send_response(code)
                self.send_header('Content-Type', 'text/plain' if mode == 'content_type' else 'application/json')
                self.send_header('Content-Length', str(len(body)))
                for k, v in extra.items():
                    self.send_header(k, v)
                self.end_headers()
                try:
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass
            def log_message(self, *args):
                pass
        parsed = urlsplit(checks['destination'])
        self.server = ThreadingHTTPServer(('127.0.0.1', parsed.port), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.server.shutdown(); self.server.server_close(); self.thread.join(1)


def sandbox_command(server, port):
    if sys.platform != 'darwin' or not Path('/usr/bin/sandbox-exec').is_file():
        raise RuntimeError('network_isolation_unavailable')
    profile = f'(version 1)(allow default)(deny network*)(allow network-outbound (remote ip "localhost:{port}"))'
    return ['/usr/bin/sandbox-exec', '-p', profile, sys.executable, str(server / 'runtime.py'), str(server / 'manifest.json')]


async def isolation_probe(command, allowed):
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0)); listener.listen()
        denied = listener.getsockname()[1]
        script = 'import socket,sys; s=socket.socket(); s.settimeout(1); s.connect(("127.0.0.1",int(sys.argv[1])))'
        for port, success in [(allowed, True), (denied, False)]:
            p = await asyncio.create_subprocess_exec(*command[:4], '-c', script, str(port), env=environment(), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            out, err = await asyncio.wait_for(p.communicate(), 2)
            assert len(out) + len(err) <= CAP
            assert (p.returncode == 0) is success, ('network_isolation_probe', port, p.returncode)
            if not success:
                assert b'Operation not permitted' in err, 'denial_was_not_os_policy'



@asynccontextmanager
async def sdk_transport(command, cwd):
    """Bounded pipes for the official Client, inside the verifier's kill group.

    The SDK's default subprocess transport starts a separate process group.
    Owning these pipes directly keeps forced verifier cancellation able to kill
    every generated-server process within the same two-second cleanup bound.
    """
    process = await asyncio.create_subprocess_exec(*command, env=environment(), cwd=cwd,
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE, limit=CAP)
    tasks = []
    try:
        incoming_send, incoming_receive = anyio.create_memory_object_stream(1)
        outgoing_send, outgoing_receive = anyio.create_memory_object_stream(1)
        captured = 0
        async def reader():
            nonlocal captured
            async with incoming_send:
                try:
                    while raw := await process.stdout.readline():
                        captured += len(raw)
                        if captured > CAP:
                            raise ValueError('sdk_child_output_limit')
                        await incoming_send.send(SessionMessage(MESSAGE_ADAPTER.validate_json(raw)))
                except (ValueError, OSError) as exc:
                    await incoming_send.send(exc)
        async def writer():
            async with outgoing_receive:
                async for item in outgoing_receive:
                    process.stdin.write((item.message.model_dump_json(by_alias=True, exclude_unset=True) + '\n').encode())
                    await process.stdin.drain()
            process.stdin.close()
        async def stderr():
            nonlocal captured
            while raw := await process.stderr.read(8192):
                captured += len(raw)
                if captured > CAP:
                    raise ValueError('sdk_child_output_limit')
        tasks = [asyncio.create_task(fn()) for fn in [reader, writer, stderr]]
        yield incoming_receive, outgoing_send
    finally:
        if process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), .5)
            except TimeoutError:
                process.kill(); await process.wait()
        for task in tasks:
            if not task.done():
                task.cancel()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception) and not isinstance(result, (anyio.ClosedResourceError, anyio.BrokenResourceError, BrokenPipeError)):
                raise result


class RPC:
    """Wire client with bounded stdout/stderr and explicit child ownership."""
    def __init__(self, command, cwd):
        self.command, self.cwd, self.total = command, cwd, 0
        self.pending = {}
        self.next_id = 0
        self.messages = []

    async def __aenter__(self):
        self.p = await asyncio.create_subprocess_exec(*self.command, env=environment(), cwd=self.cwd,
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, limit=CAP)
        self.reader = asyncio.create_task(self.read())
        self.err_reader = asyncio.create_task(self.drain_err())
        return self

    async def read(self):
        while raw := await self.p.stdout.readline():
            self.total += len(raw)
            assert self.total <= CAP, 'stdout_limit'
            message = json.loads(raw)
            assert message.get('jsonrpc') == '2.0', 'stdout_not_protocol'
            self.messages.append(message)
            pending = self.pending.pop(message.get('id'), None)
            if pending and not pending.done():
                pending.set_result(message)

    async def drain_err(self):
        while raw := await self.p.stderr.read(8192):
            self.total += len(raw)
            assert self.total <= CAP, 'stderr_limit'

    async def send(self, message):
        self.p.stdin.write((json.dumps(message) + '\n').encode()); await self.p.stdin.drain()

    async def request(self, method, params=None, *, meta=True):
        self.next_id += 1
        ident = self.next_id
        params = dict(params or {})
        if meta:
            params.setdefault('_meta', META)
        future = asyncio.get_running_loop().create_future()
        self.pending[ident] = future
        await self.send({'jsonrpc': '2.0', 'id': ident, 'method': method, 'params': params})
        return await asyncio.wait_for(future, 8)

    async def __aexit__(self, *args):
        self.p.stdin.close()
        try:
            await asyncio.wait_for(self.p.wait(), .5)
        except TimeoutError:
            self.p.terminate()
            try:
                await asyncio.wait_for(self.p.wait(), .5)
            except TimeoutError:
                self.p.kill(); await self.p.wait()
        for task in [self.reader, self.err_reader]:
            if not task.done():
                task.cancel()
        results = await asyncio.gather(self.reader, self.err_reader, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                raise result
        assert self.p.returncode is not None


async def check(server):
    checks = json.loads((server / 'checks.json').read_bytes())
    manifest = json.loads((server / 'manifest.json').read_bytes())
    validate_checks(checks, manifest['destination'])
    port = urlsplit(checks['destination']).port
    command = sandbox_command(server, port)
    with Fixture(checks) as service, tempfile.TemporaryDirectory(prefix='agent32-server-cwd-') as cwd:
        await isolation_probe(command, port)
        # Actual official Client negotiation proves discover, current revision,
        # tool schemas and fixture results independently of raw wire assertions.
        async with Client(sdk_transport(command, cwd), read_timeout_seconds=8, cache=None) as client:
            assert client.protocol_version == VERSION
            assert client.session.discover_result is not None
            tools = (await client.list_tools()).tools
            expected = checks['tool_schemas']
            assert len(tools) == len(expected) and {t.name for t in tools} == set(expected)
            # Authored fixture contracts are independent of the emitted dispatch table.
            # Successful calls alone cannot prove that clients discover the right schema.
            for tool in tools:
                assert tool.input_schema == expected[tool.name]['input_schema'], 'advertised_input_schema'
                assert tool.output_schema == expected[tool.name]['output_schema'], 'advertised_output_schema'
            for case in checks['cases']:
                result = await client.call_tool(case['tool'], case['arguments'])
                assert not result.is_error and result.structured_content == case['result']
                assert service.calls[-1] == {'path': case['path'], 'authorization': 'Bearer synthetic-fixture-token' if case['bearer'] else None}
            assert len(service.calls) == len(checks['cases']), 'pagination_or_retry'
        async with RPC(command, cwd) as rpc:
            discover = await rpc.request('server/discover')
            assert VERSION in discover['result']['supportedVersions']
            good = checks['cases'][0]
            def call(arguments=None):
                return rpc.request('tools/call', {'name': good['tool'], 'arguments': good['arguments'] if arguments is None else arguments})
            before = len(service.calls)
            missing = await rpc.request('tools/list', meta=False)
            assert 'error' in missing
            version = await rpc.request('tools/list', {'_meta': {**META, 'io.modelcontextprotocol/protocolVersion': '2999-01-01'}})
            assert 'error' in version
            unknown = await rpc.request('tools/call', {'name': 'payment_write', 'arguments': {}})
            assert 'error' in unknown
            malformed = await rpc.request('tools/call', {'name': 42})
            assert 'error' in malformed
            for bad in [{}, {'query': {'email': 42}}, {**good['arguments'], 'unknown': 1}, {'query': {'email': 'x', 'extra': 1}}]:
                result = await call(bad)
                assert result['result']['isError'] is True
            huge = await call({'query': {'email': 'x' * 9000}})
            assert huge['result']['isError'] is True
            assert len(service.calls) == before, 'invalid_arguments_caused_io'
            # Path values cannot become slash, traversal or a second destination.
            path_case = next(c for c in checks['cases'] if c['arguments'].get('path'))
            name = next(iter(path_case['arguments']['path']))
            for value in ['..', '../x', '%2e%2e', 'a/b', 'a\\b', 'a?x', 'a#x']:
                args = {**path_case['arguments'], 'path': {name: value}}
                result = await rpc.request('tools/call', {'name': path_case['tool'], 'arguments': args})
                assert result['result']['isError'] is True
            assert len(service.calls) == before
            for mode, code in [('status_401', 'upstream_status_401'), ('status_403', 'upstream_status_403'), ('status_404', 'upstream_status_404'), ('status_429', 'upstream_status_429'), ('status_500', 'upstream_status_500'), ('redirect', 'upstream_status_302'), ('json', 'upstream_json'), ('schema', 'upstream_schema'), ('oversize', 'response_limit'), ('content_type', 'upstream_content_type'), ('encoding', 'upstream_encoding'), ('slow', 'upstream_timeout')]:
                service.mode = mode
                n = len(service.calls)
                result = await call()
                assert result['result']['isError'] is True, mode
                encoded = json.dumps(result)
                assert code in encoded and 'PRIVATE_UPSTREAM_BODY' not in encoded and 'synthetic-fixture-token' not in encoded, (mode, result)
                assert len(service.calls) == n + 1, 'retry'
            service.mode = 'concurrent'
            n = len(service.calls)
            results = await asyncio.gather(*(call() for _ in range(5)))
            assert sum('concurrency_limit' in json.dumps(r) for r in results) == 1
            assert len(service.calls) == n + 4
            service.mode = 'cancel'
            # Send cancellation only after the fixture observes the request; no
            # response for this id may appear after the cancellation notification.
            cancel_id = rpc.next_id + 100
            n = len(service.calls)
            await rpc.send({'jsonrpc': '2.0', 'id': cancel_id, 'method': 'tools/call', 'params': {'name': good['tool'], 'arguments': good['arguments'], '_meta': META}})
            for _ in range(100):
                if len(service.calls) > n:
                    break
                await asyncio.sleep(.01)
            assert len(service.calls) == n + 1
            await rpc.send({'jsonrpc': '2.0', 'method': 'notifications/cancelled', 'params': {'requestId': cancel_id, 'reason': 'fixture cancellation'}})
            await asyncio.sleep(1)
            assert not any(m.get('id') == cancel_id for m in rpc.messages), 'late_cancelled_response'
            service.mode = 'normal'
            assert 'result' in await rpc.request('tools/list')
    return {'result': 'passed', 'protocol': VERSION, 'network_isolation': 'sandbox-exec-fixture-port-only',
            'scope': ['official-client-discovery', 'metadata', 'tool-schemas', 'exact-http-auth-and-encoding', 'invalid-arguments-no-io', 'upstream-failures-no-retry-or-leak', 'concurrency', 'request-cancellation', 'child-cleanup', 'denied-nonfixture-loopback'],
            'fixture_calls': len(service.calls)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--server', type=Path, default=Path(__file__).parent)
    args = parser.parse_args()
    try:
        result = asyncio.run(check(args.server.resolve()))
    except BaseException:
        # No upstream body/credential/traceback escapes this fixed gate.
        print('fixture_gate_failed', file=sys.stderr)
        raise
    print(json.dumps(result))


if __name__ == '__main__':
    main()

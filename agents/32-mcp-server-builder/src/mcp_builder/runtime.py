"""Standalone MCP runtime copied byte-for-byte into generated packages.

A manifest binds each public tool to one GET operation and source-derived JSON
schemas. It is data, never executable code. Each process owns four invocation
slots; each call owns one bounded HTTP request and no durable state. MCP metadata
is handled by the SDK, never treated as an upstream credential.
"""
import asyncio
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import quote, urlencode, urlsplit, unquote

import httpx
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.shared.exceptions import MCPError

MAX_RESPONSE = 256 * 1024


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate_json_key')
            result[key] = value
        return result
    try:
        value = json.loads(raw, object_pairs_hook=pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite_json')))
        pending = [(value, 0)]
        while pending:
            item, depth = pending.pop()
            if depth > 64:
                raise ValueError('json_depth')
            if isinstance(item, dict):
                pending.extend((child, depth + 1) for child in item.values())
            elif isinstance(item, list):
                pending.extend((child, depth + 1) for child in item)
        return value
    except (RecursionError, OverflowError):
        raise ValueError('json_complexity') from None


def schema_profile(schema, depth=0):
    """Reject schema semantics this adapter cannot preserve, before SDK use."""
    if depth > 12 or not isinstance(schema, dict):
        raise ValueError('schema_depth_or_shape')
    kind = schema.get('type')
    fields = {'type', 'title', 'description', 'enum'}
    fields |= {'object': {'properties', 'required', 'additionalProperties'},
               'array': {'items', 'minItems', 'maxItems'},
               'string': {'minLength', 'maxLength'},
               'number': {'minimum', 'maximum'},
               'integer': {'minimum', 'maximum'}, 'boolean': set(), 'null': set()}.get(kind, set())
    if kind not in {'object', 'array', 'string', 'number', 'integer', 'boolean', 'null'} or set(schema) - fields:
        raise ValueError('unsupported_schema')
    if kind == 'object':
        if schema.get('additionalProperties') is not False or not isinstance(schema.get('properties', {}), dict):
            raise ValueError('open_object')
        props = schema.get('properties', {})
        required = schema.get('required', [])
        if not isinstance(required, list) or len(set(required)) != len(required) or set(required) - set(props):
            raise ValueError('schema_required')
        for child in props.values():
            schema_profile(child, depth + 1)
    elif kind == 'array':
        schema_profile(schema.get('items'), depth + 1)
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError:
        raise ValueError('schema_shape') from None
    return schema


def validate(schema, value):
    # jsonschema distinguishes bool from integer and never coerces strings.
    if not Draft202012Validator(schema).is_valid(value):
        raise ValueError('schema_mismatch')
    if len(json.dumps(value, allow_nan=False).encode()) > 2 * 1024 * 1024:
        raise ValueError('value_limit')


def destination(url):
    parsed = urlsplit(url)
    if parsed.username or parsed.password or parsed.query or parsed.fragment or not parsed.hostname:
        raise ValueError('destination')
    if parsed.scheme != 'https' and not (parsed.scheme == 'http' and parsed.hostname == '127.0.0.1' and parsed.port):
        raise ValueError('https_required')
    if unquote(parsed.path) != parsed.path or '..' in parsed.path or '//' in parsed.path:
        raise ValueError('base_path')
    return parsed


def manifest_load(path):
    raw = Path(path).read_bytes()
    if len(raw) > 2 * 1024 * 1024:
        raise ValueError('manifest_limit')
    m = strict_json(raw)
    if set(m) != {'version', 'destination', 'credential_env', 'tools', 'hashes'} or m['version'] != 1:
        raise ValueError('manifest_fields')
    destination(m['destination'])
    if m['credential_env'] is not None and not re.fullmatch(r'[A-Z][A-Z0-9_]{0,63}', m['credential_env']):
        raise ValueError('credential_name')
    if not isinstance(m['tools'], list) or not 1 <= len(m['tools']) <= 3:
        raise ValueError('tool_limit')
    names = set()
    for t in m['tools']:
        if set(t) != {'name', 'description', 'operation', 'pointer', 'path', 'parameters', 'input_schema', 'output_schema', 'bearer'}:
            raise ValueError('tool_fields')
        if not re.fullmatch(r'[a-z][a-z0-9_]{0,63}', t['name']) or t['name'] in names:
            raise ValueError('tool_name')
        names.add(t['name'])
        if not isinstance(t['description'], str) or not 1 <= len(t['description']) <= 500:
            raise ValueError('description')
        if not isinstance(t['bearer'], bool) or (t['bearer'] and not m['credential_env']):
            raise ValueError('bearer')
        if not t['path'].startswith('/') or any(c in t['path'] for c in ['?', '#', '\\', '%', '..', '//']):
            raise ValueError('path_template')
        if t['operation'] != 'GET ' + t['path']:
            raise ValueError('operation_binding')
        slots = re.findall(r'\{([^{}]+)\}', t['path'])
        if set(slots) != {p['name'] for p in t['parameters'] if p['in'] == 'path'}:
            raise ValueError('path_binding')
        for p in t['parameters']:
            if set(p) != {'in', 'name', 'required', 'schema'} or p['in'] not in {'path', 'query'}:
                raise ValueError('parameter_binding')
            schema_profile(p['schema'])
            if p['schema']['type'] not in {'string', 'integer', 'number', 'boolean'} or not isinstance(p['required'], bool) or not isinstance(p['name'], str) or (p['in'] == 'path' and not p['required']):
                raise ValueError('parameter_scalar')
        groups = {}
        for location in ['path', 'query']:
            members = [p for p in t['parameters'] if p['in'] == location]
            if members:
                groups[location] = {'type': 'object', 'properties': {p['name']: p['schema'] for p in members}, 'required': [p['name'] for p in members if p['required']], 'additionalProperties': False}
        expected = {'type': 'object', 'properties': groups, 'required': [key for key, value in groups.items() if value['required']], 'additionalProperties': False}
        if t['input_schema'] != expected:
            raise ValueError('input_schema_binding')
        schema_profile(t['input_schema']); schema_profile(t['output_schema'])
    return m


class Runtime:
    """Per-process dispatch; excess callers fail immediately without HTTP I/O."""
    def __init__(self, manifest):
        self.manifest = manifest
        self.tools = {t['name']: t for t in manifest['tools']}
        self.active = 0

    async def list_tools(self, ctx, params):
        return types.ListToolsResult(tools=[types.Tool(
            name=t['name'], description=t['description'], input_schema=t['input_schema'],
            output_schema=t['output_schema'], annotations=types.ToolAnnotations(
                read_only_hint=True, destructive_hint=False, open_world_hint=True))
            for t in self.tools.values()])

    async def call_tool(self, ctx, params):
        if params.name not in self.tools:
            raise MCPError(-32602, 'unknown_tool')
        if self.active >= 4:
            return self.error('concurrency_limit')
        self.active += 1
        try:
            return await self.invoke(self.tools[params.name], params.arguments or {})
        finally:
            self.active -= 1

    @staticmethod
    def error(code):
        return types.CallToolResult(content=[types.TextContent(type='text', text=code)], is_error=True)

    async def invoke(self, tool, args):
        try:
            if len(json.dumps(args, allow_nan=False).encode()) > 8192:
                return self.error('argument_limit')
            validate(tool['input_schema'], args)
            path = tool['path']
            query = []
            for p in tool['parameters']:
                group = args.get(p['in'], {})
                if p['name'] not in group:
                    continue
                value = group[p['name']]
                value = str(value).lower() if isinstance(value, bool) else str(value)
                if p['in'] == 'path':
                    # Encoded separators and repeated percent-encoding must never
                    # acquire path semantics after intermediary URL decoding.
                    if any(c in value for c in '/\\%?#') or value in {'.', '..'} or any(ord(c) < 32 for c in value):
                        return self.error('unsafe_path_value')
                    path = path.replace('{' + p['name'] + '}', quote(value, safe=''))
                else:
                    query.append((p['name'], value))
            url = self.manifest['destination'].rstrip('/') + path
            if query:
                url += '?' + urlencode(query)
            headers = {'Accept': 'application/json', 'Accept-Encoding': 'identity'}
            if tool['bearer']:
                token = os.environ.get(self.manifest['credential_env'])
                if not token or not token.isascii() or any(ord(c) < 33 or ord(c) > 126 for c in token):
                    return self.error('credential_unavailable')
                headers['Authorization'] = 'Bearer ' + token
            # trust_env=False excludes proxies and ambient certificate settings.
            # No redirects or retries; cancellation closes this request context.
            async with asyncio.timeout(5):
                async with httpx.AsyncClient(trust_env=False, follow_redirects=False, timeout=5) as client:
                    async with client.stream('GET', url, headers=headers) as response:
                        if response.status_code != 200:
                            return self.error('upstream_status_' + str(response.status_code))
                        if response.headers.get('content-type', '').split(';')[0].strip() != 'application/json':
                            return self.error('upstream_content_type')
                        if response.headers.get('content-encoding', '').lower() not in {'', 'identity'}:
                            return self.error('upstream_encoding')
                        body = bytearray()
                        async for chunk in response.aiter_bytes():
                            body.extend(chunk)
                            if len(body) > MAX_RESPONSE:
                                return self.error('response_limit')
            try:
                value = strict_json(body)
            except (ValueError, UnicodeError):
                return self.error('upstream_json')
            try:
                validate(tool['output_schema'], value)
            except ValueError:
                return self.error('upstream_schema')
            return types.CallToolResult(content=[types.TextContent(type='text', text=json.dumps(value, ensure_ascii=True))], structured_content=value)
        except ValueError:
            return self.error('invalid_arguments')
        except (TimeoutError, httpx.TimeoutException):
            return self.error('upstream_timeout')
        except httpx.HTTPError:
            return self.error('upstream_transport')


async def run(path):
    runtime = Runtime(manifest_load(path))
    server = Server('generated-customer-tools', version='0.1.0',
                    on_list_tools=runtime.list_tools, on_call_tool=runtime.call_tool)
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == '__main__':
    try:
        asyncio.run(run(sys.argv[1] if len(sys.argv) == 2 else Path(__file__).with_name('manifest.json')))
    except (ValueError, OSError, KeyError, TypeError, IndexError):
        print('startup_rejected', file=sys.stderr)
        raise SystemExit(2)

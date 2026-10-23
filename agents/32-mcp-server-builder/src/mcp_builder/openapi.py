"""Parse the deliberate OpenAPI 3.1.1 subset without network reference fetching.

Operation identity is METHOD + source path, independent of optional operationId.
The catalogue records unsupported operations as data so unrelated omissions stay
visible while required unsupported operations reject compilation.
"""
import copy
import json
import re
from urllib.parse import unquote
from .runtime import schema_profile, destination

METHODS = {'get', 'put', 'post', 'delete', 'patch', 'options', 'head', 'trace'}


def ptr(value):
    return value.replace('~', '~0').replace('/', '~1')


def policy_validate(p):
    if set(p) != {'destination', 'allowed_operations', 'required_operations', 'read_only_attested', 'credential_env'}:
        raise ValueError('policy_fields')
    destination(p['destination'])
    if p['read_only_attested'] is not True:
        raise ValueError('read_only_attestation')
    for field in ['allowed_operations', 'required_operations']:
        if not isinstance(p[field], list) or len(p[field]) != len(set(p[field])) or not all(isinstance(k, str) and k.startswith('GET /') for k in p[field]):
            raise ValueError('policy_operations')
    if not set(p['required_operations']) <= set(p['allowed_operations']):
        raise ValueError('required_not_allowed')
    if p['credential_env'] is not None and not re.fullmatch(r'[A-Z][A-Z0-9_]{0,63}', p['credential_env']):
        raise ValueError('credential_env')
    return p


class Resolver:
    """Acyclic local-schema expansion with total work and serialized-size caps."""
    def __init__(self, document):
        self.document = document
        self.count = 0
        self.size = 0

    def resolve(self, value, stack=(), depth=0):
        if depth > 12:
            raise ValueError('reference_depth')
        if isinstance(value, dict):
            if '$ref' in value:
                ref = value['$ref']
                if set(value) != {'$ref'} or not isinstance(ref, str) or not ref.startswith('#/components/schemas/') or ref in stack:
                    raise ValueError('reference_unsupported')
                self.count += 1
                if self.count > 200:
                    raise ValueError('reference_count')
                target = self.document
                try:
                    for part in ref[2:].split('/'):
                        target = target[unquote(part).replace('~1', '/').replace('~0', '~')]
                except (KeyError, TypeError):
                    raise ValueError('reference_missing') from None
                expanded = self.resolve(target, stack + (ref,), depth + 1)
                self.size += len(json.dumps(expanded).encode())
                if self.size > 2 * 1024 * 1024:
                    raise ValueError('reference_size')
                return expanded
            return {k: self.resolve(v, stack, depth + 1) for k, v in value.items()}
        if isinstance(value, list):
            return [self.resolve(v, stack, depth + 1) for v in value]
        return value


def security(document, operation, policy):
    requirements = operation.get('security', document.get('security', []))
    if requirements == []:
        return False
    if not isinstance(requirements, list) or len(requirements) != 1 or not isinstance(requirements[0], dict) or len(requirements[0]) != 1:
        raise ValueError('security_combination')
    name, scopes = next(iter(requirements[0].items()))
    scheme = document.get('components', {}).get('securitySchemes', {}).get(name)
    if scopes != [] or not isinstance(scheme, dict) or scheme.get('type') != 'http' or scheme.get('scheme') != 'bearer' or set(scheme) - {'type', 'scheme', 'description', 'bearerFormat'} or not policy['credential_env']:
        raise ValueError('security_unsupported')
    return True


def operation_compile(document, path, item, method, operation, policy, resolver):
    if method != 'get' or 'requestBody' in operation:
        raise ValueError('only_get_without_body')
    if 'servers' in item or 'servers' in operation:
        raise ValueError('server_override')
    if '$ref' in item:
        raise ValueError('path_item_reference_unsupported')
    if not path.startswith('/') or any(c in path for c in ['%', '?', '#', '\\', '..', '//']):
        raise ValueError('source_path')
    params = {}
    for level in [item.get('parameters', []), operation.get('parameters', [])]:
        if not isinstance(level, list):
            raise ValueError('parameter_list')
        seen = set()
        for p in level:
            if not isinstance(p, dict) or set(p) - {'name', 'in', 'required', 'schema', 'style', 'explode', 'allowReserved', 'description', 'deprecated'}:
                raise ValueError('parameter_fields')
            key = (p.get('in'), p.get('name'))
            if key in seen or key[0] not in {'path', 'query'} or not isinstance(key[1], str) or not key[1]:
                raise ValueError('parameter_identity')
            seen.add(key)
            if p.get('style', 'simple' if key[0] == 'path' else 'form') != ('simple' if key[0] == 'path' else 'form') or p.get('allowReserved', False) is not False or not isinstance(p.get('required', False), bool):
                raise ValueError('parameter_serialization')
            if 'explode' in p and not isinstance(p['explode'], bool):
                raise ValueError('parameter_explode')
            schema = resolver.resolve(p.get('schema'))
            schema_profile(schema)
            if schema['type'] not in {'string', 'integer', 'number', 'boolean'} or (key[0] == 'path' and p.get('required') is not True):
                raise ValueError('parameter_scalar_required')
            params[key] = {'in': key[0], 'name': key[1], 'required': p.get('required', False), 'schema': schema}
    if set(re.findall(r'\{([^{}]+)\}', path)) != {name for loc, name in params if loc == 'path'}:
        raise ValueError('path_parameters')
    responses = operation.get('responses', {})
    success = [code for code in responses if str(code).startswith('2')]
    if success != ['200'] or not isinstance(responses['200'], dict) or set(responses['200'].get('content', {})) != {'application/json'}:
        raise ValueError('success_response')
    if '$ref' in responses['200']:
        raise ValueError('response_reference_unsupported')
    output = resolver.resolve(responses['200']['content']['application/json'].get('schema'))
    schema_profile(output)
    groups = {}
    required_groups = []
    for loc in ['path', 'query']:
        members = [p for p in params.values() if p['in'] == loc]
        if members:
            groups[loc] = {'type': 'object', 'properties': {p['name']: p['schema'] for p in members}, 'additionalProperties': False, 'required': [p['name'] for p in members if p['required']]}
            if groups[loc]['required']:
                required_groups.append(loc)
    return {'operation': 'GET ' + path, 'path': path, 'parameters': list(params.values()), 'input_schema': {'type': 'object', 'properties': groups, 'required': required_groups, 'additionalProperties': False}, 'output_schema': output, 'bearer': security(document, operation, policy), 'pointer': '#/paths/' + ptr(path) + '/' + method}


def catalogue(document, policy):
    if not isinstance(document, dict) or document.get('openapi') != '3.1.1' or 'jsonSchemaDialect' in document:
        raise ValueError('openapi_version_or_dialect')
    if document.get('servers') != [{'url': policy['destination']}]:
        raise ValueError('root_servers')
    components = document.get('components', {})
    if not isinstance(components, dict) or any(not isinstance(components[name], dict) for name in ('schemas', 'securitySchemes') if name in components):
        raise ValueError('components_shape')
    paths = document.get('paths')
    if not isinstance(paths, dict):
        raise ValueError('paths')
    result, coverage, identities = {}, [], set()
    resolver = Resolver(document)
    for path, item in paths.items():
        if not isinstance(item, dict):
            raise ValueError('path_item')
        for method, op in item.items():
            if method not in METHODS:
                continue
            key = method.upper() + ' ' + path
            if len(coverage) >= 50 or not isinstance(op, dict):
                raise ValueError('operation_limit_or_shape')
            if 'operationId' in op:
                if not isinstance(op['operationId'], str) or op['operationId'] in identities:
                    raise ValueError('duplicate_operation_id')
                identities.add(op['operationId'])
            row = {'operation': key, 'pointer': '#/paths/' + ptr(path) + '/' + method}
            try:
                compiled = operation_compile(document, path, item, method, op, policy, resolver)
                if key not in policy['allowed_operations']:
                    raise ValueError('policy_not_allowed')
                result[key] = compiled
                row.update(status='eligible-but-unselected', reason='allowed_supported')
            except (ValueError, KeyError, TypeError) as exc:
                row.update(status='unsupported', reason=str(exc) if isinstance(exc, ValueError) else 'source_shape')
            coverage.append(row)
    if set(policy['required_operations']) - set(result):
        raise ValueError('required_operation_unsupported')
    return result, coverage

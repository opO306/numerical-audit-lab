"""Serialization and immutable accepted-case identities, without proof logic."""
import hashlib
import json
from pathlib import Path

BASE = 'runtime_trace/regular_2step'
COMPONENTS = ('numeric_ir.json', 'v2_correspondence.json', 'endpoint.json', 'components.json')
CASE_PINS = {
    'known': {
        'directory': 'known-03', 'caller': 'audited-attempt-05-readproof-01',
        'acquisition_id': 'bf97f02a9cae33f5f74f4434657fe4713317e983b98dd8fe190fbf306e51f253',
        'seal': '300a3e988db6508ff619b20d4a4e8701f4df341908e00b64fb99b1a310b74976',
        'structure': 'ee6b63cd65a26178334a384eef5e0744bb88a1141d50276a3bfde6ccf5b44b67',
    },
    'fresh': {
        'directory': 'fresh-03', 'caller': 'fresh-closure-fresh-01-readproof-01',
        'acquisition_id': '38ab2e4a892b8513ecf0b30a12e4e7fdaa0bedd7e6786c0837c0a1387cffa249',
        'seal': 'da84bbb93d47303a1937b20aaf2eaeca02300800f0da2a7c0eba1338273ecf43',
        'structure': '3e5209c02eedbfb7faa30bf62615cfe4d10c0529c97d6d8e84e03b3f001c305a',
    },
}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError('duplicate JSON key: ' + key)
        result[key] = value
    return result


def load(path):
    return json.loads(Path(path).read_bytes(), object_pairs_hook=_pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def write(path, value):
    Path(path).write_bytes(canonical(value))


def namespaced(value, namespace):
    """Only rename graph references, preserving every other byte/ordering field."""
    if isinstance(value, dict):
        return {k: namespaced(v, namespace) for k, v in value.items()}
    if isinstance(value, list):
        return [namespaced(v, namespace) for v in value]
    if isinstance(value, str) and value.startswith('v:'):
        return namespace + '/' + value
    return value


def sid(value_id, offset=0):
    return f'state:{value_id}:byte:{offset}'


def completion(chain):
    return digest({k: v for k, v in chain.items() if k != 'completion_sha256'})


def component_hashes(out):
    return [{'path': name, 'sha256': sha(Path(out) / name)} for name in COMPONENTS]

"""Single attempt authority: the pinned 25-row compatibility table."""
import hashlib
from functools import lru_cache
from types import MappingProxyType
from .spec import load_spec
from .wire import canonical_bytes, integer, WireFailure

INITIAL_DIGEST = hashlib.sha256(b'LAB_C1B1_ATTEMPTS_V1\0').digest()


@lru_cache(maxsize=1)
def compatibility_table():
    rows=load_spec().wire['attempt_tuple_contract']['compatibility_table']
    table={(r['producer'],r['rechecker']):r['allowed_reasons'] for r in rows}
    if len(rows)!=25 or len(table)!=25:
        raise ValueError('incomplete attempt table')
    return MappingProxyType(table)


def validate_attempt(obj):
    if type(obj) is not dict or set(obj)!={'t','N','P','producer','rechecker','reason'}:
        raise ValueError('attempt keys')
    if any(type(obj[k]) is not str for k in ('producer','rechecker')):
        raise ValueError('attempt status type')
    if obj['reason'] is not None and type(obj['reason']) is not str:
        raise ValueError('attempt reason type')
    if obj['reason'] not in compatibility_table().get((obj['producer'],obj['rechecker']),()):
        raise ValueError('incompatible attempt')
    try:
        t=integer(obj['t']);n=integer(obj['N'],positive=True);p=integer(obj['P'],positive=True)
    except WireFailure as err:
        if err.reason=='HOST_SERIALIZATION_LIMIT':raise
        raise ValueError('attempt integer') from None
    if t<0 or n<1 or p<8:
        raise ValueError('attempt parameters')
    return obj


def append_attempt(previous, obj):
    if type(previous) is not bytes or len(previous)!=32:
        raise ValueError('raw digest32 required')
    validate_attempt(obj)
    return hashlib.sha256(previous+canonical_bytes(obj)).digest()

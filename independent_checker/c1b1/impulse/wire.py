"""Bounded canonical framing. No process-global decimal conversion changes."""
import hashlib
import json
import re

INTEGER_LIMIT = 10**4096
INT_RE = re.compile(r'(?:0|-?[1-9][0-9]*)\Z', re.ASCII)
HASH_RE = re.compile(r'[0-9a-f]{64}\Z', re.ASCII)


class WireFailure(Exception):
    def __init__(self, reason, kind=None):
        self.reason, self.kind = reason, kind
        super().__init__(reason)


def decimal(value):
    if type(value) is not int:
        raise WireFailure('SCHEMA_INVALID')
    if abs(value) >= INTEGER_LIMIT:
        raise WireFailure('ARTIFACT_LIMIT', 'ARTIFACT_BYTES')
    try:
        return str(value)
    except ValueError:
        raise WireFailure('HOST_SERIALIZATION_LIMIT', 'HOST_DECIMAL') from None


def integer(text, positive=False):
    if type(text) is not str or not INT_RE.fullmatch(text) or len(text.lstrip('-')) > 4096:
        raise WireFailure('SCHEMA_INVALID')
    try:
        value = int(text)
    except ValueError:
        raise WireFailure('HOST_SERIALIZATION_LIMIT', 'HOST_DECIMAL') from None
    if positive and value <= 0:
        raise WireFailure('SCHEMA_INVALID')
    return value


def canonical_bytes(obj, cap=1048576):
    """Count each ASCII chunk before appending; never serialize then measure."""
    chunks, size = [], 0
    def emit(piece):
        nonlocal size
        size += len(piece)
        if size > cap:
            raise WireFailure('ARTIFACT_LIMIT', 'ARTIFACT_BYTES')
        chunks.append(piece)
    def visit(value, depth=1):
        if depth > 7:
            raise WireFailure('SCHEMA_INVALID')
        if value is None:
            emit(b'null')
        elif type(value) is str:
            if len(value) > cap - size:
                raise WireFailure('ARTIFACT_LIMIT', 'ARTIFACT_BYTES')
            emit(b'"')
            for char in value:
                emit(json.dumps(char, ensure_ascii=True)[1:-1].encode('ascii'))
            emit(b'"')
        elif type(value) is dict:
            if any(type(k) is not str for k in value):
                raise WireFailure('SCHEMA_INVALID')
            emit(b'{')
            for i, key in enumerate(sorted(value)):
                if i: emit(b',')
                visit(key, depth); emit(b':'); visit(value[key], depth+1)
            emit(b'}')
        elif type(value) is list:
            if len(value) > 12:
                raise WireFailure('SCHEMA_INVALID')
            emit(b'[')
            for i, item in enumerate(value):
                if i: emit(b',')
                visit(item, depth+1)
            emit(b']')
        else:
            raise WireFailure('SCHEMA_INVALID')
    visit(obj); emit(b'\n')
    return b''.join(chunks)


def parse(data):
    if type(data) is not bytes:
        raise WireFailure('SCHEMA_INVALID')
    if len(data) > 1048576:
        raise WireFailure('RESOURCE_CAP', 'PARSE_BYTES')
    # Streaming bounds precede json's containers and all int conversions.
    stack, quoted, escape = [], False, False
    for byte in data:
        if quoted:
            if escape: escape = False
            elif byte == 92: escape = True
            elif byte == 34: quoted = False
            continue
        if byte == 34: quoted = True
        elif byte in (123,91):
            stack.append([byte,0])
            if len(stack) > 7: raise WireFailure('SCHEMA_INVALID')
        elif byte == 58 and stack and stack[-1][0] == 123:
            stack[-1][1] += 1
            if stack[-1][1] > 26: raise WireFailure('SCHEMA_INVALID')
        elif byte == 44 and stack and stack[-1][0] == 91:
            stack[-1][1] += 1
            if stack[-1][1] >= 12: raise WireFailure('SCHEMA_INVALID')
        elif byte in (125,93):
            if not stack: raise WireFailure('SCHEMA_INVALID')
            stack.pop()
    def no_number(_):
        raise WireFailure('SCHEMA_INVALID')
    def pairs(items):
        obj = {}
        for key, value in items:
            if key in obj: raise WireFailure('SCHEMA_INVALID')
            obj[key] = value
        return obj
    try:
        obj = json.loads(data.decode('ascii'), object_pairs_hook=pairs,
                         parse_int=no_number, parse_float=no_number, parse_constant=no_number)
    except (ValueError, UnicodeError, RecursionError):
        raise WireFailure('SCHEMA_INVALID') from None
    if canonical_bytes(obj) != data:
        raise WireFailure('SCHEMA_INVALID')
    return obj


def digest(obj, domain=None):
    prefix = b'' if domain is None else domain.encode('ascii') + b'\0'
    return hashlib.sha256(prefix + canonical_bytes(obj)).hexdigest()

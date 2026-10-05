"""Read-only loader of the independently approved exact bundle bytes."""
from dataclasses import dataclass
from fractions import Fraction as Q
import hashlib
import json
from pathlib import Path
from types import MappingProxyType

SPEC_SHA256 = '3c3773b306700b0cf2dced1a618ae73ad81c7dd4abbf36764fc6ec3191ff2bc1'
PACKAGE_SHA256 = '4a4cad78a192f72cf479cf16ceb971ea257d9bdf89acc5a7ca6e4fea3738219f'
SPEC_DIR = Path(__file__).resolve().parents[3] / 'specs/c1b1-independent-impulse-v1-attempt-reason-null'


def freeze(value):
    if type(value) is dict:
        return MappingProxyType({k:freeze(v) for k,v in value.items()})
    if type(value) is list:
        return tuple(freeze(v) for v in value)
    return value


@dataclass(frozen=True)
class FrozenSpec:
    sha256: str
    hashes: object
    constants: object
    r_min_squared: Q
    wire: object
    identity: object
    rechecker_sha256: str


def load_spec():
    def read(name, wanted):
        data=(SPEC_DIR/name).read_bytes()
        if hashlib.sha256(data).hexdigest()!=wanted:
            raise ValueError('frozen spec bytes mismatch')
        obj=json.loads(data.decode('ascii'))
        if (json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=True)+'\n').encode()!=data:
            raise ValueError('noncanonical specification')
        if (SPEC_DIR/(name+'.sha256')).read_text(encoding='ascii').split()[0]!=wanted:
            raise ValueError('sidecar mismatch')
        return obj
    package=read('package-manifest.json',PACKAGE_SHA256)
    docs={name:read(name,sha) for name,sha in package['dependencies'].items()}
    if package['dependencies']['semantic-bundle.json']!=SPEC_SHA256:
        raise ValueError('wrong semantic target')
    const={r['key']:Q(int(r['lab_canonical']['n']),int(r['lab_canonical']['d']))
           for r in docs['constants.json']['records'] if r['role']=='NOMINAL_MODEL'}
    r=docs['physical-domain.json']['r_min_squared_bohr2']
    return FrozenSpec(SPEC_SHA256,MappingProxyType(package['dependencies']),MappingProxyType(const),
        Q(int(r['n']),int(r['d'])),freeze(docs['proof-wire.json']),freeze(docs['acquisition-identity.json']),
        docs['rechecker-lineage.json']['checker_source']['raw_sha256'])

"""Read-only loader of the independently approved exact bundle bytes."""
from dataclasses import dataclass
from fractions import Fraction as Q
import hashlib
import json
from pathlib import Path
from types import MappingProxyType

SPEC_SHA256 = '11eedb45fc80d8b1f8db1bc5afdceb1754914c5e2f49ba48ad2b4d87d63bb007'
PACKAGE_SHA256 = '9d430833bb359600b4c9f67f225e9c8a74fb883d6fe119ca8b7c2502b8ce4499'
SPEC_DIR = Path(__file__).resolve().parents[3] / 'specs/c1b1-independent-impulse-v1'


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
        Q(int(r['n']),int(r['d'])),docs['proof-wire.json'],docs['acquisition-identity.json'],
        docs['rechecker-lineage.json']['checker_source']['raw_sha256'])

import hashlib
import importlib.util
import io
import json
from pathlib import Path
import zipfile
import pytest

spec=importlib.util.spec_from_file_location('manifest_package',Path(__file__).resolve().parents[1]/'tools/gate2c1_package.py')
pkg=importlib.util.module_from_spec(spec);spec.loader.exec_module(pkg)

def archive(internal):
    b=io.BytesIO()
    with zipfile.ZipFile(b,'w') as z:
        z.writestr('present',b'ok')
        if internal is not None:z.writestr('PACKAGE_MANIFEST.json',internal)
    b.seek(0);return b

def valid_manifest():
    return {'schema':'gate2c1-complete-audit-package-v1',
            'files':{'present':hashlib.sha256(b'ok').hexdigest()},'required_members':['present']}

@pytest.mark.parametrize('mutation',['missing','invalid','hash','schema','required'])
def test_internal_manifest_mutations_are_rejected(mutation):
    d=valid_manifest();raw=json.dumps(d)
    if mutation=='missing':raw=None
    elif mutation=='invalid':raw='INVALID INTERNAL MANIFEST'
    elif mutation=='hash':d['files']['present']='0'*64;raw=json.dumps(d)
    elif mutation=='schema':d['schema']='wrong';raw=json.dumps(d)
    else:d['required_members']=[];raw=json.dumps(d)
    with pytest.raises(ValueError):pkg.validate_members(archive(raw),valid_manifest()['files'],['present'])

def test_valid_internal_manifest_is_accepted():
    d=valid_manifest()
    assert pkg.validate_members(archive(json.dumps(d)),d['files'],d['required_members'])==1

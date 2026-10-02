"""Delivery mutations that reproduce the missing-vendor / wrong-ZIP findings."""
import hashlib
import importlib.util
import json
from pathlib import Path
import zipfile

import pytest

P=Path(__file__).resolve().parents[1]/'tools/gate2c1_package.py'
spec=importlib.util.spec_from_file_location('gate2c1_package',P)
pkg=importlib.util.module_from_spec(spec);spec.loader.exec_module(pkg)

def test_missing_advertised_wheel_and_so_are_rejected(tmp_path):
    p=tmp_path/'x.zip'
    with zipfile.ZipFile(p,'w') as z:z.writestr('present',b'ok')
    h=hashlib.sha256(b'ok').hexdigest()
    with pytest.raises(ValueError):pkg.validate_members(p,{'present':h},['present','wheel.whl'])
    with pytest.raises(ValueError):pkg.validate_members(p,{'present':h},['present','binary.so'])
    assert pkg.validate_members(p,{'present':h},['present'])==1


def test_changed_zip_member_including_bundle_is_rejected(tmp_path):
    p=tmp_path/'x.zip'
    with zipfile.ZipFile(p,'w') as z:z.writestr('git/gate2c1.bundle',b'changed')
    with pytest.raises(ValueError):pkg.validate_members(p,{'git/gate2c1.bundle':hashlib.sha256(b'original').hexdigest()},[])


def test_document_receipt_and_actual_zip_must_agree(tmp_path):
    p=tmp_path/'only-deliver-this.zip'
    with zipfile.ZipFile(p,'w') as z:z.writestr('present',b'ok')
    h=hashlib.sha256(p.read_bytes()).hexdigest()
    record={'zip_file':p.name,'zip_sha256':h}
    (tmp_path/'delivery_receipt.json').write_text(json.dumps(record))
    (tmp_path/'DELIVERY.md').write_text(f'{p.name}\nSHA-256: `{h}`\n')
    (tmp_path/(p.name+'.sha256')).write_text(f'{h}  {p.name}\n')
    assert pkg.verify_delivery(tmp_path)==h
    (tmp_path/'DELIVERY.md').write_text(f'{p.name}\nSHA-256: `'+('0'*64)+'`\n')
    with pytest.raises(ValueError):pkg.verify_delivery(tmp_path)
    (tmp_path/'DELIVERY.md').write_text(f'{p.name}\nSHA-256: `{h}`\n')
    record['zip_file']='another-workspace.zip'
    (tmp_path/'delivery_receipt.json').write_text(json.dumps(record))
    with pytest.raises((ValueError,OSError)):pkg.verify_delivery(tmp_path)

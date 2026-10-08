"""Role-separated ELF checks, TEST_ONLY; no inferior or profile authority."""
import copy
import hashlib
import struct
from pathlib import Path
import pytest
from compute_metabolism.v0 import evex_profile as gate
from verified_driver.v1.native_evex_checker import _elf

def executable(tmp_path):
    # Literal independent ET_EXEC ELF64: executable load covers the entry,
    # and separate PT_NOTE holds one GNU Build ID.
    raw=bytearray(1024)
    raw[:16]=b'\x7fELF\x02\x01\x01'+bytes(9)
    struct.pack_into('<HHIQQQIHHHHHH',raw,16,2,62,1,0x400100,64,0,0,64,56,2,0,0,0)
    struct.pack_into('<IIQQQQQQ',raw,64,1,5,0,0x400000,0,1024,1024,0x1000)
    struct.pack_into('<IIQQQQQQ',raw,120,4,4,0x200,0,0,20,20,4)
    raw[0x200:0x214]=struct.pack('<III',4,4,3)+b'GNU\0'+bytes.fromhex('12345678')
    path=tmp_path/'python';path.write_bytes(raw)
    expected=dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),build_id='12345678')
    return path,expected,raw

def test_approved_et_exec_runtime_reaches_identity_success(tmp_path):
    path,expected,_=executable(tmp_path)
    result=gate._executable_identity(path,expected)
    assert result==dict(resolved_path=str(path),sha256=expected['sha256'],build_id='12345678')

def test_et_exec_cannot_impersonate_shared_library(tmp_path):
    path,expected,_=executable(tmp_path)
    with pytest.raises(ValueError,match='shared library'):gate._library_identity(path,expected)

@pytest.mark.parametrize('attack',['hash','buildid','type_dyn','type_rel','machine','class','endian','version','phoff','phsize','phnum','filebound','loadsize','address','noteheader','notebody','missingid','entry','noexec'])
def test_executable_rejects_wrong_identity_or_damaged_structure(tmp_path,attack):
    path,expected,raw=executable(tmp_path)
    if attack=='hash':expected['sha256']='ff'*32
    elif attack=='buildid':expected['build_id']='deadbeef'
    elif attack=='type_dyn':struct.pack_into('<H',raw,16,3)
    elif attack=='type_rel':struct.pack_into('<H',raw,16,1)
    elif attack=='machine':struct.pack_into('<H',raw,18,183)
    elif attack=='class':raw[4]=1
    elif attack=='endian':raw[5]=2
    elif attack=='version':struct.pack_into('<I',raw,20,2)
    elif attack=='phoff':struct.pack_into('<Q',raw,32,1000)
    elif attack=='phsize':struct.pack_into('<H',raw,54,48)
    elif attack=='phnum':struct.pack_into('<H',raw,56,0)
    elif attack=='filebound':struct.pack_into('<Q',raw,64+32,1025)
    elif attack=='loadsize':struct.pack_into('<Q',raw,64+40,1023)
    elif attack=='address':struct.pack_into('<Q',raw,64+16,(1<<64)-100)
    elif attack=='noteheader':struct.pack_into('<Q',raw,120+32,8)
    elif attack=='notebody':struct.pack_into('<I',raw,0x204,9999)
    elif attack=='missingid':raw[0x20c:0x210]=b'BAD\0'
    elif attack=='entry':struct.pack_into('<Q',raw,24,0x500000)
    elif attack=='noexec':struct.pack_into('<I',raw,64+4,4)
    path.write_bytes(raw)
    if attack not in ('hash','buildid'):expected['sha256']=hashlib.sha256(raw).hexdigest()
    with pytest.raises(ValueError):gate._executable_identity(path,expected)

def test_executable_refuses_unapproved_path_and_replacement(tmp_path):
    path,expected,raw=executable(tmp_path)
    other=tmp_path/'unapproved';other.write_bytes(raw)
    with pytest.raises(ValueError):gate._executable_identity(other,expected)
    replacement=tmp_path/'replacement';replacement.write_bytes(raw[:-1]+b'\x01');replacement.replace(path)
    with pytest.raises(ValueError):gate._executable_identity(path,expected)

def test_explicit_prepared_link_allowed_but_wrong_target_refuses(tmp_path):
    path,expected,raw=executable(tmp_path)
    link=tmp_path/'venv-python';link.symlink_to(path)
    result=gate._executable_identity(link,expected,approved_paths=(str(link),))
    assert result['resolved_path']==str(path)
    other=tmp_path/'other';other.write_bytes(raw)
    link.unlink();link.symlink_to(other)
    with pytest.raises(ValueError):gate._executable_identity(link,expected,approved_paths=(str(link),))

def test_et_dyn_library_rules_unchanged(tmp_path):
    path,expected,raw=executable(tmp_path);struct.pack_into('<H',raw,16,3)
    path.write_bytes(raw);expected['sha256']=hashlib.sha256(raw).hexdigest()
    assert gate._library_identity(path,expected)['build_id']=='12345678'
    with pytest.raises(ValueError):gate._executable_identity(path,expected)
    struct.pack_into('<H',raw,18,183);path.write_bytes(raw);expected['sha256']=hashlib.sha256(raw).hexdigest()
    with pytest.raises(ValueError):gate._library_identity(path,expected)

def test_executable_identity_followed_by_full_independent_thirteen_replay(tmp_path):
    # Hand-authored states are checked by independent semantics, never a
    # recorded-post oracle. A post-identity mask mutation must still refuse.
    from test_compute_metabolism_gala_origin import fixture,LIBC,GALA
    path,expected,_=executable(tmp_path);gate._executable_identity(path,expected)
    doc,root,fp,sources,birth=fixture(tmp_path)
    result=gate.verify_observation(doc,root,fp,sources,LIBC,GALA,birth)
    assert result['native']['instruction_count']==13
    doc['native']['steps'][10]['after']['registers']['k1']^=1
    with pytest.raises(ValueError):gate.verify_observation(doc,root,fp,sources,LIBC,GALA,birth)

@pytest.mark.parametrize('attack',['hash','buildid'])
def test_library_sha_and_buildid_checks_preserved(tmp_path,attack):
    path,expected,raw=executable(tmp_path);struct.pack_into('<H',raw,16,3)
    path.write_bytes(raw);expected['sha256']=hashlib.sha256(raw).hexdigest()
    expected['sha256' if attack=='hash' else 'build_id']='ff'*32
    with pytest.raises(ValueError):gate._library_identity(path,expected)

def test_executable_detects_rename_during_bounded_read(tmp_path,monkeypatch):
    path,expected,raw=executable(tmp_path)
    real=gate._bytes
    def concurrent_replacement(p,maximum):
        data=real(p,maximum)
        replacement=tmp_path/'concurrent';replacement.write_bytes(raw);replacement.replace(path)
        return data
    monkeypatch.setattr(gate,'_bytes',concurrent_replacement)
    with pytest.raises(ValueError,match='replaced during read'):gate._executable_identity(path,expected)

@pytest.mark.parametrize('attack',['ambiguousid','bigid','unalignednote','phcount','truncated'])
def test_executable_note_and_table_bounds_preserved(tmp_path,attack):
    path,expected,raw=executable(tmp_path)
    if attack=='ambiguousid':
        struct.pack_into('<H',raw,56,3)
        struct.pack_into('<IIQQQQQQ',raw,176,4,4,0x240,0,0,20,20,4)
        raw[0x240:0x254]=struct.pack('<III',4,4,3)+b'GNU\0'+bytes.fromhex('deadbeef')
    elif attack=='bigid':struct.pack_into('<I',raw,0x204,65)
    elif attack=='unalignednote':struct.pack_into('<Q',raw,120+32,19)
    elif attack=='phcount':struct.pack_into('<H',raw,56,4097)
    elif attack=='truncated':raw=raw[:63]
    path.write_bytes(raw);expected['sha256']=hashlib.sha256(raw).hexdigest()
    with pytest.raises(ValueError):gate._executable_identity(path,expected)

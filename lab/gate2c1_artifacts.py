"""Producer artifact encoding; independent checker does not import this module."""
import hashlib
import json
import struct

def float_bits(v):
    return f'{struct.unpack(">Q",struct.pack(">d",v))[0]:016x}'

def forms_bits(forms):
    return None if forms is None else [{'coefficients':[float_bits(v) for v in f.coef],
                                       'box':float_bits(f.box)} for f in forms]

def snapshot(step,st,lst,bf,lf,first_bin,first_cross,bin_dead,lab_dead):
    return {'step':step,'bin_state':[f'{v:016x}' for v in st],
            'lab_state':[f'{lst[k]:016x}' for k in ('x','y','px','py')],
            'bin_forms':forms_bits(bf),'lab_forms':forms_bits(lf),
            'first_bin':first_bin,'first_cross':first_cross,
            'bin_dead':bin_dead,'lab_dead':lab_dead}

def assert_segment_connection(end,start,step):
    if end!=start or end['step']!=step:
        raise ValueError('segment endpoint/input mismatch or coverage gap')

def encoded(d):
    return (json.dumps(d,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n').encode()

def save(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():raise ValueError(f'preserve artifact: {path}')
    blob=encoded(data);path.write_bytes(blob)
    return hashlib.sha256(blob).hexdigest()

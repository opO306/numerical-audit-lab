#!/usr/bin/env python3
"""Independent audit checker for runtime-trace-audit-d408a07 snapshot.
Does NOT import runtime_trace.gdb_capture / semantics / correspondence or machine_mapping.
"""
from pathlib import Path
from fractions import Fraction
from collections import Counter
import argparse, hashlib, json, re, struct, subprocess, tempfile, gzip

class AuditError(Exception): pass

def req(c,m):
    if not c: raise AuditError(m)

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def bhex(text,w): return int(text,16).to_bytes(w,'little')

def bits_to_frac(bits):
    s=(bits>>63)&1; e=(bits>>52)&0x7ff; f=bits&((1<<52)-1)
    if e==0x7ff: raise AuditError('nonfinite')
    if e==0:
        if f==0: return Fraction(0), s
        q=Fraction(f,1) * Fraction(1,1<<1074)
    else:
        sig=(1<<52)|f
        shift=e-1023-52
        q=Fraction(sig*(1<<shift),1) if shift>=0 else Fraction(sig,1<<(-shift))
    return (-q if s else q), s

def round_even(n,d):
    q,r=divmod(n,d)
    t=r*2
    if t>d or (t==d and (q&1)): q+=1
    return q

def floor_log2_fraction(q):
    req(q>0,'log2 positive')
    n,d=q.numerator,q.denominator
    e=n.bit_length()-d.bit_length()
    if e>=0:
        if Fraction(1<<e,1)>q: e-=1
    else:
        if Fraction(1,1<<(-e))>q: e-=1
    return e

def pow2_frac(e): return Fraction(1<<e,1) if e>=0 else Fraction(1,1<<(-e))

def fraction_to_binary64(q, sign_zero=0):
    if q==0: return (sign_zero&1)<<63
    sign=1 if q<0 else 0; a=abs(q)
    e=floor_log2_fraction(a)
    if e>1023: return (sign<<63)|(0x7ff<<52)
    if e>=-1022:
        unit=pow2_frac(e-52)
        z=a/unit
        m=round_even(z.numerator,z.denominator)
        if m==(1<<53):
            e+=1; m=1<<52
            if e>1023: return (sign<<63)|(0x7ff<<52)
        exp=e+1023; frac=m-(1<<52)
        return (sign<<63)|(exp<<52)|frac
    z=a/pow2_frac(-1074)
    m=round_even(z.numerator,z.denominator)
    if m==0: return sign<<63
    if m>=(1<<52): return (sign<<63)|(1<<52)  # rounded to min normal
    return (sign<<63)|m

def op_expected(op,a_bits,b_bits):
    # AT&T: src=a, dst=b, result dst op src
    a,sa=bits_to_frac(a_bits); b,sb=bits_to_frac(b_bits)
    if op=='mulsd': q=b*a; sz=sa^sb
    elif op=='addsd':
        q=b+a
        if q==0:
            # RN-even exact zero: same-sign zeros preserve sign; cancellation -> +0
            sz = sb if b==0 and a==0 and sa==sb else 0
        else: sz=0
    elif op=='subsd':
        q=b-a
        if q==0:
            # b + (-a); same effective sign zeros preserve, cancellation -> +0
            effa=sa^1
            sz = sb if b==0 and a==0 and sb==effa else 0
        else: sz=0
    else: raise AuditError('unsupported scalar op')
    return fraction_to_binary64(q,sz)

def reg_full(name):
    if name.startswith(('xmm','ymm','zmm')): return 'v'+re.search(r'\d+',name).group(0)
    if re.fullmatch(r'r\d+[dwb]',name): return name[:-1]
    if name.startswith('e') and len(name)==3: return 'r'+name[1:]
    if name in {'ax','bx','cx','dx'}: return 'r'+name
    if name in {'si','di','bp','sp'}: return 'r'+name
    if name in {'al','bl','cl','dl'}: return 'r'+name[0]+'x'
    if name in {'sil','dil','bpl','spl'}: return 'r'+name[:-1]
    return name

def reg_width(name):
    if name.startswith('xmm'): return 16
    if name.startswith('ymm'): return 32
    if name.startswith('zmm'): return 64
    if re.fullmatch(r'r\d+',name) or name in {'rax','rbx','rcx','rdx','rsi','rdi','rbp','rsp','rip'}: return 8
    if re.fullmatch(r'r\d+d',name) or name.startswith('e'): return 4
    if re.fullmatch(r'r\d+w',name) or name in {'ax','bx','cx','dx','si','di','bp','sp'}: return 2
    if re.fullmatch(r'r\d+b',name) or name in {'al','bl','cl','dl','sil','dil','bpl','spl'}: return 1
    raise AuditError('unknown reg '+name)

def context_reg(ctx,name,width):
    if name.startswith(('xmm','ymm','zmm')):
        txt=ctx['xmm'].get(name,ctx.get('extra_vectors',{}).get(name))
        req(txt is not None,'missing vector '+name)
        return bhex(txt,reg_width(name))[:width]
    full=reg_full(name)
    return bhex(ctx['gpr'][full],8)[:width]

def split_att(text):
    text=re.sub(r'\s+<[^>]*>','',text.split('#')[0]).strip()
    words=text.split()
    while words and words[0] in {'cs','data16'}: words.pop(0)
    req(words,'empty asm'); op=words[0]; rest=' '.join(words[1:])
    out=[]; depth=0; start=0
    for i,c in enumerate(rest):
        depth += (c=='(') - (c==')')
        if c==',' and depth==0: out.append(rest[start:i].strip()); start=i+1
    if rest: out.append(rest[start:].strip())
    return op,out

def ea(text,row):
    text=text.lstrip('*')
    m=re.fullmatch(r'([^()]*)\(([^()]*)\)',text)
    if not m: return int(text,0)
    disp=int(m.group(1),0) if m.group(1) else 0
    ps=m.group(2).split(','); ps += ['']*(3-len(ps)); base,index,scale=ps[:3]
    def rv(r):
        if not r: return 0
        if r=='%rip': return row['runtime_pc']+len(bytes.fromhex(row['bytes']))
        return int.from_bytes(context_reg(row['pre'],r[1:],8),'little')
    return (disp+rv(base)+rv(index)*int(scale or 1)) & ((1<<64)-1)

def elf_offset(image,vaddr,length):
    req(image[:6]==b'\x7fELF\x02\x01','ELF64 LE')
    phoff=struct.unpack_from('<Q',image,32)[0]; entsz,n=struct.unpack_from('<HH',image,54)
    for i in range(n):
        kind,flags,off,va,_,fsz,msz,_=struct.unpack_from('<IIQQQQQQ',image,phoff+i*entsz)
        if kind==1 and va<=vaddr and vaddr+length<=va+fsz: return off+vaddr-va
    raise AuditError('ELF offset missing')

def objdump_map(path):
    s=subprocess.check_output(['objdump','-d',str(path)],text=True,errors='replace')
    out={}
    for line in s.splitlines():
        m=re.match(r'\s*([0-9a-f]+):\s*((?:[0-9a-f]{2}\s+)+)\s*(.*)$',line)
        if m:
            addr=int(m.group(1),16); by=bytes.fromhex(''.join(m.group(2).split())); asm=m.group(3).strip()
            out[addr]=(by,asm)
    return out

def decode_raw_opcode(rawbytes):
    with tempfile.NamedTemporaryFile() as f:
        f.write(rawbytes); f.flush()
        s=subprocess.check_output(['objdump','-D','-b','binary','-m','i386:x86-64',f.name],text=True)
    for line in s.splitlines():
        m=re.match(r'\s*0:\s*(?:[0-9a-f]{2}\s+)+\s*(\S+)',line)
        if m:return m.group(1)
    raise AuditError('raw decode failed')

def canonical_opcode(op):
    return {'retq':'ret','callq':'call'}.get(op,op)

def classification(op):
    if op in {'addsd','subsd','mulsd'}: return 'ARITH'
    if op in {'movsd','movapd','movaps','movupd','movups','movdqa','movdqu','movq','movb','movw','movl','mov','vmovd','vmovdqu','vmovdqu8','vmovdqu64','vmovdqa','vmovups'}: return 'MOVE'
    if op in {'pxor','xorps','xorpd','vpxor','vpxord','vpxorq'}: return 'ZERO'
    if op=='vpbroadcastb': return 'ZERO_FILL'
    if op in {'push','pushq','pop','popq'}: return 'STACK'
    if op in {'call','callq','ret','retq'} or op.startswith('j'): return 'CONTROL'
    if op.startswith('nop') or op in {'test','testb','testl','testq','cmp','cmpb','cmpl','cmpq','lea','add','sub','and','or','xor','shl','shr','sar','inc','dec','not','neg','imul','movslq','movzbl','movzwl','endbr64','vzeroupper','xchg','bt'}: return 'ROUTING'
    return 'UNSUPPORTED'

def known_key(opnd,i):
    if opnd['kind']=='memory': return ('m',opnd['address']+i)
    if opnd['kind']=='register': return ('r',reg_full(opnd['register']),i)
    return None

def read_known(known,opnd):
    out=[]
    for i in range(opnd['width']):
        k=known_key(opnd,i)
        if k is None or k not in known:return None
        out.append(known[k])
    return bytes(out)

def write_known(known,opnd,data):
    for i,b in enumerate(data[:opnd['width']]):
        k=known_key(opnd,i)
        if k is not None: known[k]=b

def invalidate_reg(known,full):
    for k in list(known):
        if k[0]=='r' and k[1]==full: del known[k]

def control_expected(row,op,args):
    pc=row['runtime_pc']; nxt=pc+len(bytes.fromhex(row['bytes'])); flags=row['pre']['eflags']
    cf,zf,sf,of,pf=bool(flags&1),bool(flags&64),bool(flags&128),bool(flags&2048),bool(flags&4)
    if op in {'ret','retq'}: return int(row['operands'][0]['raw_bits'],16)
    if op.startswith('j') or op in {'call','callq'}:
        if args and args[0].startswith('*'): target=int(row['operands'][0]['raw_bits'],16)
        else:
            # GDB disassembly in artifact uses runtime absolute direct target.
            target=int(args[0],16)
        pred={'jmp':1,'je':zf,'jz':zf,'jne':not zf,'jnz':not zf,'jb':cf,'jae':not cf,
              'ja':not cf and not zf,'jbe':cf or zf,'jl':sf!=of,'jge':sf==of,'jg':not zf and sf==of,
              'jle':zf or sf!=of,'js':sf,'jns':not sf,'jp':pf,'jnp':not pf,'call':1,'callq':1}
        req(op in pred,'unsupported branch predicate '+op)
        return target if pred[op] else nxt
    return nxt

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('root'); ap.add_argument('--zip'); ap.add_argument('--attempt',default='attempt-05'); ap.add_argument('--out')
    a=ap.parse_args(); root=Path(a.root).resolve(); art=root/'runtime_trace/artifacts'/a.attempt
    R={'attempt':a.attempt,'errors':[],'unresolved':[],'facts':{},'checks':{}}
    if a.zip:
        R['facts']['zip_sha256']=sha(a.zip)
    cap=json.loads((art/'capture.json').read_text()); exe=json.loads((art/'execution.json').read_text()); harness=json.loads((art/'harness_output.json').read_text())
    rawstream=(art/'trace.jsonl').read_bytes(); rows=[json.loads(x) for x in rawstream.splitlines()]
    # integrity/linkage
    try:
        req(cap['verdict']=='CAPTURED','capture verdict'); req(sha(art/'trace.jsonl')==cap['trace_sha256'],'trace hash')
        req(len(rows)==cap['record_count'],'record count'); req([r['seq'] for r in rows]==list(range(len(rows))),'sequence')
        chain='0'*64
        for r in rows:
            u={k:v for k,v in r.items() if k!='chain'}
            chain=hashlib.sha256(bytes.fromhex(chain)+json.dumps(u,sort_keys=True,separators=(',',':')).encode()).hexdigest(); req(chain==r['chain'],'chain')
        req(chain==cap['final_chain'],'chain endpoint')
        regs=cap['regions']; req([(x['phase'],x['start_seq'],x['end_seq']) for x in regs]==[('init',0,regs[0]['end_seq']),('step',regs[0]['end_seq'],len(rows))],'regions')
        req(regs[0]['end_seq']==regs[1]['start_seq'],'region gap')
        for rg in regs:
            sub=rows[rg['start_seq']:rg['end_seq']]; req(sub,'empty region'); req(sub[0]['runtime_pc']==rg['entry_pc'],'entry pc'); req(sub[-1]['post_pc']==rg['return_pc'],'return pc')
            for i,r in enumerate(sub):
                req(r['phase']==rg['phase'],'phase'); req(r['pid']==sub[0]['pid'] and r['ptid']==sub[0]['ptid'],'pid/tid')
                req(r['runtime_pc']==int(r['pre']['gpr']['rip'],16),'pre rip'); req(r['post_pc']==int(r['post']['gpr']['rip'],16),'post rip')
                if i: req(sub[i-1]['post_pc']==r['runtime_pc'],'pc continuity')
                for f in ['gpr','xmm','mxcsr','eflags']: req(sub[i-1]['post'][f]==r['pre'][f],f'context continuity {f}') if i else None
        for n in ['q','full_v','latent']: req(regs[0]['end_state'][n]==regs[1]['start_state'][n],'cross-region state')
        R['checks']['integrity_linkage']='PASS'
    except Exception as e:R['checks']['integrity_linkage']='FAIL';R['errors'].append(str(e))

    # acquisition source hashes and absence of mapping read
    try:
        for rel,h in exe['source_sha256_before_execution'].items(): req(sha(root/rel)==h,'source hash '+rel)
        txt=(root/'runtime_trace/gdb_capture.py').read_text()+(root/'runtime_trace/semantics.py').read_text()
        req('machine_mapping.json' not in txt and 'T_bin' not in txt,'acquisition source references mapping')
        R['checks']['acquisition_source']='PASS'
    except Exception as e:R['checks']['acquisition_source']='FAIL';R['errors'].append(str(e))

    # module bindings + independent disassembly
    local={
      '3a15d66867d83762c7f2f1e37359cb8f6c5743edb369c65285cb0b1c4f7498bf':root/'runtime_trace/frozen_binaries/libc.so.6',
      'a6ac98736304bb9f6a92e473bba45da10d9b5b99f8019e2ca15eb6a7f86234fc':root/'audit/gate2c1/vendor/gala/integrate/cyintegrators/leapfrog.cpython-312-x86_64-linux-gnu.so',
      '33d66d82c34c717560747ffbfca1d98f97432a0a671a0a210a0a225d8367ecaf':root/'audit/gate2c1/vendor/gala/potential/potential/builtin/cybuiltin.cpython-312-x86_64-linux-gnu.so'}
    dis={h:objdump_map(p) for h,p in local.items()}
    missing=set(); decoded_ops=[]; available_records=0
    try:
        for r in rows:
            h=r['module_sha256']; op_rec=canonical_opcode(r['opcode']); b=bytes.fromhex(r['bytes'])
            req(r['runtime_pc']-r['module_load_base']==r['elf_address'],'load bias')
            mp=r['mapping']; req(mp['start']<=r['runtime_pc']<mp['end'] and 'x' in mp['perms'],'exec map')
            if h in local:
                p=local[h]; img=p.read_bytes(); req(sha(p)==h,'module hash local'); off=elf_offset(img,r['elf_address'],len(b)); req(off==r['elf_file_offset'],'file offset'); req(img[off:off+len(b)]==b,'ELF bytes')
                req(r['elf_address'] in dis[h],'objdump address'); db,asm=dis[h][r['elf_address']]; op,_=split_att(asm); req(canonical_opcode(op)==op_rec,'independent opcode decode')
                decoded_ops.append(op); available_records+=1
            else:
                missing.add(h); op=decode_raw_opcode(b); req(canonical_opcode(op)==op_rec,'raw opcode decode missing module'); decoded_ops.append(op)
        R['checks']['module_bytes_decode']='PASS' if not missing else 'PARTIAL'
        if missing:R['unresolved'].append('Original libc image for trace module hash(es) absent: '+','.join(sorted(missing)))
    except Exception as e:R['checks']['module_bytes_decode']='FAIL';R['errors'].append(str(e))
    R['facts']['verified_original_module_records']=available_records; R['facts']['missing_module_records']=len(rows)-available_records

    # control flow semantics independent of post_pc linkage
    try:
        for r in rows:
            op,args=split_att(r['instruction']); req(canonical_opcode(op)==canonical_opcode(r['opcode']),'artifact asm/opcode mismatch')
            exp=control_expected(r,op,args) if classification(op)=='CONTROL' else r['runtime_pc']+len(bytes.fromhex(r['bytes']))
            req(r['post_pc']==exp,'control-flow semantics at seq '+str(r['seq']))
        R['checks']['control_flow']='PASS'
    except Exception as e:R['checks']['control_flow']='FAIL';R['errors'].append(str(e))

    # widths + MXCSR + unsupported FP
    try:
        unsupported=[]
        for r,op in zip(rows,decoded_ops):
            cl=classification(op); req(cl!='UNSUPPORTED','unsupported executed opcode '+op)
            if cl=='ARITH': expected_kind={'addsd':'ADD','subsd':'SUB','mulsd':'MUL'}[op]
            else: expected_kind={'MOVE':'MOVE','ZERO':'ZERO','ZERO_FILL':'ZERO_FILL','STACK':'STACK','CONTROL':'CONTROL','ROUTING':'ROUTING'}[cl]
            req(r['kind']==expected_kind,'opcode/kind semantic mismatch')
            ops=r['operands']
            if op=='movslq': req([x['width'] for x in ops]==[4,8],'movslq width')
            if op=='movzbl': req([x['width'] for x in ops]==[1,4],'movzbl width')
            if op=='movzwl': req([x['width'] for x in ops]==[2,4],'movzwl width')
            if op in {'cmpb','testb'}: req(all(x['width']==1 for x in ops),'byte compare width')
            if op in {'cmpl','testl'}: req(all(x['width']==4 for x in ops),'dword compare width')
            if op in {'cmpq','testq'}: req(all(x['width']==8 for x in ops),'qword compare width')
            if op=='vpbroadcastb': req(ops[0]['width']==1,'broadcast source width')
            for c in [r['pre'],r['post']]:
                v=c['mxcsr']; req((v & ((3<<13)|(1<<15)|(1<<6)))==0,'MXCSR RC/FTZ/DAZ'); req((v&0x1f80)==0x1f80,'MXCSR masks')
            # flag any actual FP arithmetic family outside supported scalar forms
            if re.match(r'^(v?)(add|sub|mul|div|sqrt|fmadd|fmsub|fnmadd|fnmsub).*(ss|sd|ps|pd)$',op) and op not in {'addsd','subsd','mulsd'}: unsupported.append((r['seq'],op))
        req(not unsupported,'unsupported FP arithmetic '+repr(unsupported))
        R['checks']['width_mxcsr_supported_fp']='PASS'
    except Exception as e:R['checks']['width_mxcsr_supported_fp']='FAIL';R['errors'].append(str(e))

    # provenance + exact scalar arithmetic
    fp=[]
    try:
        for rg in cap['regions']:
            known={}
            for n,addr in rg['pointers'].items():
                dat=bhex(rg['start_state'][n],16)
                for i,v in enumerate(dat):known[('m',addr+i)]=v
            # boundary xmm0/xmm1 low lanes
            first=rows[rg['start_seq']]
            for n in ['xmm0','xmm1']:
                dat=context_reg(first['pre'],n,8)
                for i,v in enumerate(dat):known[('r',reg_full(n),i)]=v
            for r in rows[rg['start_seq']:rg['end_seq']]:
                op,args=split_att(r['instruction']); cl=classification(op); ops=r['operands']
                # register operand snapshots and effective addresses where asm operands align 1:1.
                if cl in {'ARITH','MOVE','ROUTING','ZERO','ZERO_FILL'}:
                    for text,o in zip(args,ops):
                        if o['kind']=='register': req(bhex(o['raw_bits'],o['width'])==context_reg(r['pre'],o['register'],o['width']),'operand register snapshot')
                        if o['kind']=='memory': req(o['address']==ea(text,r),'effective address')
                if cl in {'ARITH','MOVE'}:
                    req(len(ops)==2,'two operand '+op)
                if cl=='ARITH':
                    src,dst=ops; req(dst['kind']=='register' and dst['register'].startswith('xmm'),'scalar dst')
                    # derive sources from known state or verified ELF constant
                    vals=[]
                    for o in [src,dst]:
                        dat=read_known(known,o)
                        if dat is None and o['kind']=='memory':
                            # read-only module constant from local verified image
                            for h,p in local.items():
                                m=cap['modules'].get(next((k for k,v in cap['modules'].items() if v['sha256']==h),''),{})
                                if m and m['load_base']<=o['address']<m['load_base']+p.stat().st_size:
                                    img=p.read_bytes(); va=o['address']-m['load_base']; off=elf_offset(img,va,o['width']); dat=img[off:off+o['width']]; break
                        req(dat is not None,'unknown scalar source seq '+str(r['seq']))
                        req(dat==bhex(o['raw_bits'],o['width']),'scalar source raw mismatch')
                        vals.append(int.from_bytes(dat,'little'))
                    exp=op_expected(op,vals[0],vals[1]); post=int.from_bytes(context_reg(r['post'],dst['register'],8),'little')
                    req(post==exp,'exact RN-even mismatch seq '+str(r['seq']))
                    req(context_reg(r['pre'],dst['register'],16)[8:]==context_reg(r['post'],dst['register'],16)[8:],'scalar upper lane changed')
                    write_known(known,dst,exp.to_bytes(8,'little')); fp.append((r['seq'],op,exp))
                elif cl=='MOVE':
                    src,dst=ops
                    # source actual bytes
                    if src['kind']=='register': actual=context_reg(r['pre'],src['register'],src['width'])
                    elif src['kind']=='memory':
                        actual=read_known(known,src)
                        if actual is None: actual=bhex(src['raw_bits'],src['width'])  # nonnumeric external/control data, not promoted to known unless source known
                    elif src['kind']=='immediate': actual=bhex(src['raw_bits'],src['width'])
                    else: actual=bhex(src['raw_bits'],src['width'])
                    req(actual==bhex(src['raw_bits'],src['width']),'move source snapshot')
                    # verify destination post for reg / captured post-write for memory
                    if dst['kind']=='register': req(context_reg(r['post'],dst['register'],dst['width'])==actual[:dst['width']],'move result register')
                    else: req(bhex(r['result_bits'],dst['width'])==actual[:dst['width']],'move result memory')
                    src_known=read_known(known,src) is not None
                    if src_known: write_known(known,dst,actual[:dst['width']])
                    else:
                        # unknown moves must not establish numerical provenance
                        for i in range(dst['width']):
                            k=known_key(dst,i)
                            if k: known.pop(k,None)
                    # x86 scalar/vector load rules that deterministically zero upper bits.
                    if dst['kind']=='register' and dst['register'].startswith('xmm'):
                        if op in {'movq','vmovd'} or (op=='movsd' and src['kind']=='memory'):
                            for i in range(dst['width'],16): known[('r',reg_full(dst['register']),i)]=0
                    # x86 32-bit gpr writes zero-extend
                    if dst['kind']=='register' and reg_width(dst['register'])==4 and not dst['register'].startswith('xmm'):
                        for i in range(4,8):known[('r',reg_full(dst['register']),i)]=0
                elif cl=='STACK':
                    # Captured push/pop are explicit bit copies with [source,destination].
                    if len(ops)==2:
                        src,dst=ops
                        if src['kind']=='register': actual=context_reg(r['pre'],src['register'],src['width'])
                        elif src['kind']=='memory': actual=read_known(known,src) or bhex(src['raw_bits'],src['width'])
                        else: actual=bhex(src['raw_bits'],src['width'])
                        req(actual==bhex(src['raw_bits'],src['width']),'stack source snapshot')
                        if dst['kind']=='register': req(context_reg(r['post'],dst['register'],dst['width'])==actual[:dst['width']],'stack result register')
                        else: req(bhex(r['result_bits'],dst['width'])==actual[:dst['width']],'stack result memory')
                        if read_known(known,src) is not None: write_known(known,dst,actual[:dst['width']])
                        else:
                            for i in range(dst['width']):
                                k=known_key(dst,i)
                                if k: known.pop(k,None)
                elif cl=='ZERO':
                    if ops:
                        dst=ops[-1]; data=b'\0'*dst['width']; write_known(known,dst,data)
                elif cl=='ZERO_FILL':
                    req(ops and int(ops[0]['raw_bits'],16)&0xff==0,'broadcast nonzero'); dst=ops[-1]; write_known(known,dst,b'\0'*dst['width'])
                elif cl=='ROUTING':
                    # integer XOR reg,reg establishes exact zero; other changed tracked GPRs invalidate and would break later numerical use.
                    if op=='xor' and len(args)==2 and args[0]==args[1] and ops:
                        dst=ops[-1]; write_known(known,dst,b'\0'*dst['width'])
                    for name in r['pre']['gpr']:
                        if name!='rip' and r['pre']['gpr'][name]!=r['post']['gpr'][name]:
                            if not (op=='xor' and ops and reg_full(ops[-1].get('register',''))==name): invalidate_reg(known,name)
                # STACK/CONTROL do not carry tracked numeric payload in this trace
            for n,addr in rg['pointers'].items():
                got=bytes(known.get(('m',addr+i),-1) for i in range(16)) if all(('m',addr+i) in known for i in range(16)) else None
                req(got is not None and got==bhex(rg['end_state'][n],16),'endpoint provenance '+rg['phase']+' '+n)
        R['checks']['provenance_exact_fp']='PASS'
    except Exception as e:R['checks']['provenance_exact_fp']='FAIL';R['errors'].append(str(e))
    R['facts']['scalar_fp_count']=len(fp); R['facts']['scalar_by_opcode']=dict(Counter(op for _,op,_ in fp)); R['facts']['scalar_by_phase']={p:sum(1 for r in rows if r['phase']==p and r['opcode'] in {'addsd','subsd','mulsd'}) for p in ['init','step']}

    # function/module coverage from independently verified records
    try:
        syms=Counter(r['symbol'] for r in rows)
        req(any('c_init_velocity' in s for s in syms),'init symbol'); req(any('c_leapfrog_step' in s for s in syms),'step symbol'); req(any(s=='c_gradient' for s in syms),'c_gradient'); req(any('henon_heiles_gradient' in s for s in syms),'HH gradient')
        req(any(r['module_sha256'].startswith('33d66') and 'henon_heiles_gradient' in r['symbol'] for r in rows),'HH cybuiltin module')
        R['checks']['function_coverage']='PASS'
    except Exception as e:R['checks']['function_coverage']='FAIL';R['errors'].append(str(e))

    # endpoint fixture directly
    try:
        endpoint=cap['regions'][-1]['end_state']; got=[]
        for n in ['q','full_v']:
            d=bhex(endpoint[n],16); got += [f'0x{struct.unpack_from("<Q",d,8*i)[0]:016x}' for i in range(2)]
        req(got==harness['output_bits'],'trace/harness endpoint')
        man=json.loads((root/'benchmarks/gate2b/fixtures/cloud-2026-10-01/manifest.json').read_text()); rawf=gzip.decompress((root/'benchmarks/gate2b/fixtures/cloud-2026-10-01/regular_forward.u64.gz').read_bytes())
        req(hashlib.sha256(rawf).hexdigest()==man['files']['regular_forward']['sha256_raw'],'fixture raw hash'); shape=man['files']['regular_forward']['shape']
        exp=[f'0x{struct.unpack_from("<Q",rawf,8*(i*shape[1]+1))[0]:016x}' for i in range(4)]
        req(got==exp,'fixture endpoint'); R['checks']['endpoint_fixture']='PASS'; R['facts']['endpoint_bits']=got
    except Exception as e:R['checks']['endpoint_fixture']='FAIL';R['errors'].append(str(e))

    # thread/MXCSR facts
    R['facts']['ptids']=sorted({tuple(r['ptid']) for r in rows}); R['facts']['pids']=sorted({r['pid'] for r in rows}); R['facts']['mxcsr_values']=sorted({r[c]['mxcsr'] for r in rows for c in ['pre','post']})
    R['facts']['opcodes']=dict(Counter(r['opcode'] for r in rows)); R['facts']['record_count']=len(rows)
    R['verdict']='FAIL' if R['errors'] else ('CONDITIONAL' if R['unresolved'] else 'PASS')
    out=json.dumps(R,indent=2,sort_keys=True)
    print(out)
    if a.out: Path(a.out).write_text(out+'\n')
    return 1 if R['errors'] else 0
if __name__=='__main__': raise SystemExit(main())

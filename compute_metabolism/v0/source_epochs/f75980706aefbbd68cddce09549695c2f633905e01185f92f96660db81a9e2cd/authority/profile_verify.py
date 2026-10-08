"""Independent, bounded native-profile gate; observation is never authority.

Numerical code is imported only from the existing independent V1 checker.
Reviewed LIVE anchors authenticate provenance, not a PASS label. Every accepted
anchor is replayed through raw/checkpoint/edge verification and fresh semantic
negative controls. Adding an anchor is a reviewed source change; observers and
candidate generators cannot supply their own trusted anchors. The first anchor
covers only the audited Gala gradient memset domain (16 bytes, zero fill).
"""
from __future__ import annotations

from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import tempfile
from types import MappingProxyType


# Historical evidence remains immutable. Future independently reviewed LIVE
# evidence may add an anchor with its own exact domain and V1 source binding.
# Such a change must also change the adaptive-layer source binding.
REVIEWED_LIVE_ANCHORS = MappingProxyType({
    'task8-positive-03-edge-1': MappingProxyType(dict(
        relative_directory='verified_driver/v1/artifacts/task8/positive-03/runs/actual',
        checkpoint_name='checkpoint-1', derived_name='edge-1', predecessor_name='edge-1.predecessor.json',
        source_binding='f75980706aefbbd68cddce09549695c2f633905e01185f92f96660db81a9e2cd', source_count=40,
        target_entry=1611648, lengths=(16,), fill_values=(0,),
        required_cpu_features=('avx2', 'erms'), capability_rank=10,
        default_profile_id='libc-memset-avx2-unaligned-erms-v1',
        proof_files_sha256=MappingProxyType({
            'checkpoint.json':'8c49ea95af86f29bd7d7cf188370ac5ca2fe8ed90058bc7987d5e62c7acd3a93',
            'trace.jsonl':'f8bc9cef81e40383270b11717890fc1fb5c02d9ff4da144e565f57668151d692',
            'edge.json':'ac7cf83c37a1e5dad6c1f68a9ef80f4098280f4ca4da621218e479e738273180',
            'completion.json':'c2213fa639bf5414f3d106efc00aa744cf96bc2bdfb2f37a046e88ffc8535d3f',
            'predecessor.json':'9979a2b110d16b283d5995912608f37817c5713270d46528c652083cb22e4c9e'})))})


def _require(value, reason):
    if not value:
        raise ValueError(reason)


def _canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _unalias(path):
    path = Path(path).absolute()
    _require('..' not in path.parts and not any(p.is_symlink() for p in (path,*path.parents)),
             'unaliased evidence path required')
    return path


def _bytes(path, maximum=16*1024*1024):
    path = _unalias(path)
    _require(path.is_file() and path.stat().st_nlink == 1 and path.stat().st_size <= maximum,
             'bounded single-link evidence required')
    return path.read_bytes()


def _json(path):
    def pairs(items):
        result = {}
        for key,value in items:
            _require(key not in result, 'duplicate proof/profile key')
            result[key] = value
        return result
    return json.loads(_bytes(path), object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite evidence value')))


def _child(directory, relative):
    p = Path(relative)
    _require(type(relative) is str and relative and not p.is_absolute()
             and '..' not in p.parts and ':' not in relative and '\\' not in relative,
             'proof namespace escape')
    result = _unalias(directory/p)
    _require(result.is_relative_to(directory), 'proof namespace escape')
    return result


def _flat(context, prefix=''):
    result = {}
    for name,value in context.items():
        label = prefix+name
        if isinstance(value,dict):
            result.update(_flat(value,label+'.'))
        else:
            result[label] = value
    return result


_MODEL_OPS = frozenset(('mov movb movw movl movq movsd vmovd vmovdqu movdqu movzbl lea '
    'vpbroadcastb pop leave ret push call add addb addw addl addq sub subb subw subl subq '
    'and andb andw andl andq or orb orw orl orq xor xorb xorw xorl xorq cmp cmpb cmpw cmpl cmpq '
    'test testb testw testl testq shl shlb shlw shll shlq shr shrb shrw shrl shrq setne xchg cmpxchg '
    'jmp ja jb jbe je jge jle jne endbr64 nop nopw nopl addsd subsd mulsd movapd movslq imul jae').split())


def _model_form(assembly):
    """Finite operand-form recognition, without claiming execution correctness."""
    from runtime_trace.caller_transition import checker as c
    from runtime_trace.regular_nstep import machine_check as m
    try:
        normalized = m.effect_assembly(assembly)
        mnemonic,args = c._parse_assembly(normalized)
        base = mnemonic.removeprefix('lock ')
        if base not in _MODEL_OPS:
            return False, False, 'UNKNOWN_MNEMONIC'
        # The audited model has XMM/GPR semantics, not AVX512/opmask/upper YMM.
        for register in re.findall(r'%([a-z][a-z0-9]*)',','.join(args)):
            _require(register in c.ALIASES or register in ('rip','fs','gs')
                     or re.fullmatch(r'xmm(?:[0-9]|1[0-5])',register), 'register class unmodelled')
        arity = (0 if base in {'nop','nopw','nopl','endbr64','ret','leave'} else
                 1 if base in {'pop','push','call','jmp','ja','jb','jbe','je','jge','jle','jne','jae','setne'} else 2)
        _require(len(args)==arity, 'unsupported operand count')
        if arity==2:
            _require(all(a.startswith(('%','$')) or c._is_memory_operand(a) for a in args),
                     'audited AT&T operand dialect required')
        if base in {'mov','movb','movw','movl','movq','movzbl','lea','movslq'}:
            _require(not any('%xmm' in a for a in args), 'integer/vector operand mismatch')
        if base in {'movsd','vmovd','vmovdqu','movdqu','vpbroadcastb','movapd','addsd','subsd','mulsd'}:
            _require(any('%xmm' in a for a in args), 'missing modelled XMM operand')
        if base in {'xchg','cmpxchg'}:
            _require(c._is_memory_operand(args[1]), 'audited exchange requires memory destination')
        if base in {'vmovdqu','movdqu'}:
            _require(args[0].startswith('%xmm') and c._is_memory_operand(args[1]),
                     'audited packed move supports XMM store direction')
        if base in {'movapd','addsd','subsd','mulsd'}:
            _require(args[1].startswith('%xmm'), 'audited body vector destination is XMM')
        if len(args)==2:
            _require(not (c._is_memory_operand(args[0]) and c._is_memory_operand(args[1])), 'memory-to-memory form')
        return True, True, None
    except Exception:
        return False, True, 'UNSUPPORTED_OPERAND_FORM'


def _unknown(row, reason):
    assembly = row['assembly']
    return dict(sequence=row['seq'], pc=row['pc'], instruction_bytes=row.get('instruction_bytes',row.get('bytes')),
        assembly=assembly, reason=reason,
        actual_inputs=copy.deepcopy(row.get('before',row.get('pre',{}))),
        actual_outputs=copy.deepcopy(row.get('after',row.get('post',{}))),
        memory_effects=dict(reads=copy.deepcopy(row.get('reads',[])), writes=copy.deepcopy(row.get('writes',[])),
            complete=False, unknown=copy.deepcopy(row.get('unknown_effects',['effects outside measured window']))),
        required_rule=dict(decode='bind exact instruction bytes at pinned library ELF PC',
            registers='derive every defined output register, flags, mask and upper vector lane from the captured input',
            memory='derive all read/write addresses, widths, same-value writes and conditional effects; prove no other writes',
            control='derive next PC, caller, return target and permitted entry independently',
            domain='state supported operand forms, alignment, mask, length, fill byte and exceptional cases'),
        positive_test=dict(instruction_bytes=row.get('instruction_bytes',row.get('bytes')), assembly=assembly,
            input=copy.deepcopy(row.get('before',row.get('pre',{}))),
            output=copy.deepcopy(row.get('after',row.get('post',{}))),
            reads=copy.deepcopy(row.get('reads',[])),writes=copy.deepcopy(row.get('writes',[])),
            expected='independent semantics must reproduce all captured defined outputs and effects'),
        negative_tests=[dict(mutation=mutation, expected='REFUSED', rule=rule) for mutation,rule in (
            ('changed_output','flip one defined output bit while keeping inputs'),
            ('outside_destination_write','add one byte write at destination+length'),
            ('unmodelled_register_change','change one preserved GPR, upper vector lane or mask'),
            ('instruction_bytes','change one opcode byte without changing the claimed assembly'),
            ('missing_same_value_write','delete a derived write whose old and new bytes match'),
            ('caller_or_entry','substitute the caller ELF address or resolved library entry'))])


def _observation_decode(rows,library):
    """Independently decode pinned bytes; display dialect is not a new opcode."""
    from runtime_trace.regular_2step import structure
    from runtime_trace.caller_transition import checker as c
    digest=library.get('sha256') if isinstance(library,dict) else None
    frozen=structure._frozen_modules(_unalias(Path(__file__).parents[2]))
    if digest not in frozen:
        return {},None
    path,_=frozen[digest]
    addresses={row.get('pc') for row in rows if type(row.get('pc')) is int and row['pc']>=0}
    try:
        return c._objdump_decode(path,digest,addresses,'objdump'),None
    except Exception as exc:
        return {},'PINNED_CODE_DECODE_REFUSED: '+str(exc)


def inspect_observation(observation):
    """Analyze evidence gaps; even a matching endpoint grants no promotion."""
    _require(observation.get('schema')=='COMPUTE_METABOLISM_OBSERVATION_V1'
             and observation.get('mode')=='OBSERVATION'
             and observation.get('certified_state_progress') is False, 'non-certified observation required')
    _canonical(observation)
    rows = observation.get('trace')
    _require(isinstance(rows,list) and 0<len(rows)<=100000, 'bounded nonempty observation trace required')
    decoded,decode_error=_observation_decode(rows,observation.get('library'))
    reads=[]; writes=[]; unknown=[]; changed=set(); known=0; checked=0; unsupported=0
    for index,row in enumerate(rows):
        _require(row.get('seq')==index and type(row['seq']) is int
                 and type(row.get('pc')) is int and row['pc']>=0
                 and type(row.get('assembly')) is str and 0<len(row['assembly'])<=4096,
                 'dense observation sequence, ELF PC and assembly required')
        for field,target in (('reads',reads),('writes',writes)):
            _require(isinstance(row.get(field),list), 'observed memory ranges required')
            for item in row[field]:
                _require(type(item.get('address')) is int and item['address']>=0
                    and type(item.get('size')) is int and 0<item['size']<=1048576
                    and item['address']+item['size']<=1<<64, 'bounded actual memory range required')
                target.append(copy.deepcopy(item))
        before=_flat(row.get('before',row.get('pre',{}))); after=_flat(row.get('after',row.get('post',{})))
        changed.update(name for name in set(before)|set(after) if before.get(name)!=after.get(name))
        assembly=row['assembly']; code_error=decode_error
        if row['pc'] in decoded:
            encoded,assembly=decoded[row['pc']]
            if encoded!=row.get('instruction_bytes',row.get('bytes')):
                code_error='PINNED_INSTRUCTION_BYTES_MISMATCH'
        supported,mnemonic_known,reason=_model_form(assembly)
        if code_error: supported=False; reason=code_error
        if supported:
            known+=1
            # Actual re-evaluation is available only for complete audited native
            # context/effect rows, never a collector's completeness boolean.
            if all(k in row for k in ('pre','post','module_sha256','elf_address','possible_memory_writes','pre_memory_observations')):
                try:
                    from runtime_trace.regular_nstep import machine_check as m, raw_check as r
                    native=m.normalized(row); native_decode={native['sequence']:m.effect_assembly(assembly)}
                    m.registers([native],native_decode); m.controls([native],native_decode,{row['module_sha256']:row.get('load_base',0)})
                    m.writes([native],native_decode); r._memory([native],native_decode)
                    checked+=1
                except Exception as exc:
                    unknown.append(_unknown(row,'INDEPENDENT_EFFECT_RECHECK_REFUSED: '+str(exc)))
        else:
            unsupported+=int(mnemonic_known); item=_unknown(row,reason)
            item['independently_decoded_assembly']=assembly if row['pc'] in decoded else None
            unknown.append(item)
    required=['AUTHENTICATED_LIVE_PROOF_BUNDLE','FULL_RAW_CHECKPOINT_EDGE_REPLAY',
              'FULL_NATIVE_CONTEXT_AND_EFFECTS','PINNED_LIBRARY_HASH_BUILD_ID_AND_CODE',
              'APPROVED_GALA_CALL_ORIGIN_AND_ACTUAL_ENTRY','EXACT_INPUT_DOMAIN_AND_SIDE_EFFECT_CONTRACT',
              'NEGATIVE_CONTROLS_REPLAY','CURRENT_V1_AND_PROFILE_GATE_SOURCE_BINDINGS']
    if unknown: required.append('INDEPENDENT_NEW_INSTRUCTION_SEMANTICS')
    return dict(reads=reads,writes=writes,changed_registers=sorted(changed),
        effect_coverage=dict(status='INCOMPLETE',complete=False,observed_rows=len(rows),
            independently_checked_rows=checked,collector_claimed_complete_rows=sum(r.get('memory_effects_complete') is True for r in rows),
            reason='observed windows and mnemonics do not prove all effects or authenticated numerical authority'),
        instruction_counts=dict(total=len(rows),model_known=known,independently_checked=checked,
            explained=checked,needs_new_semantics=len(unknown),known_mnemonic_unsupported=unsupported),
        unknown_instructions=unknown,required_proofs=required,promotion_allowed=False,numerical_certification=False)


def _build_id(raw):
    _require(raw[:6]==b'\x7fELF\x02\x01' and len(raw)>=64, 'ELF64 little-endian library required')
    start=struct.unpack_from('<Q',raw,32)[0]; stride,count=struct.unpack_from('<HH',raw,54)
    _require(stride>=56 and count<=1024 and start+stride*count<=len(raw), 'ELF program headers')
    found=[]
    for index in range(count):
        kind,_,offset,_,_,size,_,_=struct.unpack_from('<IIQQQQQQ',raw,start+index*stride)
        if kind!=4: continue
        end=offset+size; _require(end<=len(raw),'bounded ELF note'); cursor=offset
        while cursor+12<=end:
            namesz,descsz,note=struct.unpack_from('<III',raw,cursor); cursor+=12
            name=raw[cursor:cursor+namesz]; cursor+=(namesz+3)&~3
            value=raw[cursor:cursor+descsz]; cursor+=(descsz+3)&~3
            _require(cursor<=end,'complete ELF note')
            if note==3 and name==b'GNU\0' and value: found.append(value.hex())
    _require(len(set(found))==1,'unique GNU Build-ID required')
    return found[0]


def _paths(directory, bundle):
    return (_child(directory,bundle['checkpoint_directory']),_child(directory,bundle['derived_directory']),
            _child(directory,bundle['predecessor']))


def _anchor_paths(root,anchor):
    base=_child(root,anchor['relative_directory'])
    original=(_child(base,anchor['checkpoint_name']),_child(base,anchor['derived_name']),
              _child(base,anchor['predecessor_name']))
    if any(p.exists() for p in original):
        _require(all(p.exists() for p in original),'incomplete original LIVE proof; bundled fallback forbidden')
        return original
    # Ignored historical files may be absent from deployment. Repackaged exact
    # bytes are source-owned and authenticate to the identical reviewed anchor.
    bundled=_child(root,'compute_metabolism/v0/execution_profiles/proofs/'+
                   next(key for key,value in REVIEWED_LIVE_ANCHORS.items() if value is anchor))
    return (_child(bundled,'checkpoint'),_child(bundled,'edge'),_child(bundled,'predecessor.json'))


def _authenticate(paths,anchor):
    checkpoint,derived,predecessor=paths
    actual={'checkpoint.json':_sha(_bytes(checkpoint/'checkpoint.json')),
        'trace.jsonl':_sha(_bytes(checkpoint/'trace.jsonl',536870912)),
        'edge.json':_sha(_bytes(derived/'edge.json')), 'completion.json':_sha(_bytes(derived/'completion.json')),
        'predecessor.json':_sha(_bytes(predecessor))}
    _require(actual==dict(anchor['proof_files_sha256']), 'independently reviewed LIVE evidence anchor mismatch')
    _require(_bytes(checkpoint/'CHECKPOINT',65)==(actual['checkpoint.json']+'\n').encode(),'checkpoint anchor pointer')
    document=_json(checkpoint/'checkpoint.json')
    _require(document['metadata'].get('evidence_role')=='LIVE', 'TEST_ONLY/synthetic proof cannot grant VERIFIED')
    _require(document['metadata']['source_binding']==anchor['source_binding']
             and len(document['metadata']['source_snapshot'])==anchor['source_count'], 'reviewed complete source binding')
    return document,actual


def _profile_contract(paths,anchor,root,profile_id=None):
    """Derive only the exact anchored call domain; no producer evaluator."""
    from runtime_trace.regular_2step import structure
    checkpoint,_,_=paths; document=_json(checkpoint/'checkpoint.json'); capture=document['metadata']['capture']
    rows=[json.loads(line) for line in _bytes(checkpoint/'trace.jsonl',536870912).splitlines()]
    frozen=structure._frozen_modules(root)
    libc_hash=next(m['sha256'] for p,m in capture['modules'].items() if p.endswith('/libc.so.6'))
    gala_hash=next(m['sha256'] for p,m in capture['modules'].items() if '/gala/' in p and '/integrate/' in p)
    runtime_hash=next(m['sha256'] for p,m in capture['modules'].items() if p.endswith('/python3.12'))
    calls=[]; path=set(); changed=set(); origins=set()
    for index,row in enumerate(rows):
        if row['module_sha256']!=libc_hash or row['elf_address']!=anchor['target_entry']: continue
        _require(index>0 and rows[index-1]['module_sha256']==gala_hash,'approved Gala memset caller required')
        caller=rows[index-1]; origins.add((caller['module_sha256'],caller['elf_address']))
        end=index
        while end<len(rows) and rows[end]['module_sha256']==libc_hash: end+=1
        _require(end<len(rows) and rows[end]['module_sha256']==gala_hash,'complete memset return to Gala required')
        execution=rows[index:end]; pre=row['pre']; post=execution[-1]['post']
        destination=int(pre['gpr']['rdi'],16); length=int(pre['gpr']['rdx'],16); fill=int(pre['gpr']['rsi'],16)&255
        _require(length in anchor['lengths'] and fill in anchor['fill_values'], 'exact reviewed memset input domain')
        gradient=capture['regions'][0]['pointers']['gradient']
        _require(destination==gradient,'approved Gala gradient destination')
        _require(int(post['gpr']['rax'],16)==destination,'exact memset return pointer')
        for name in ('rbx','rbp','r12','r13','r14','r15'):
            _require(pre['gpr'][name]==post['gpr'][name],'callee-saved register preserved')
        covered=set()
        for current in execution:
            path.add(current['elf_address']); before=_flat(current['pre']); after=_flat(current['post'])
            changed.update(n for n in set(before)|set(after) if before.get(n)!=after.get(n))
            for write in current['possible_memory_writes']:
                address=write['address']; width=write['size']
                _require(destination<=address and address+width<=destination+length,'no outside-destination memset write')
                raw=bytes.fromhex(write.get('after_hex','')) if 'after_hex' in write else int(write['after_bits'],16).to_bytes(width,'little')
                _require(raw==bytes([fill])*width,'independent exact fill bytes')
                covered.update(range(address-destination,address-destination+width))
        _require(covered==set(range(length)),'all destination bytes written, including same-value stores')
        calls.append(dict(length=length,fill=fill))
    _require(calls and {(c['length'],c['fill']) for c in calls}==
             {(length,fill) for length in anchor['lengths'] for fill in anchor['fill_values']},
             'entire declared finite input domain exercised')
    pid=profile_id or anchor['default_profile_id']
    _require(type(pid) is str and re.fullmatch('[a-z0-9][a-z0-9-]{0,95}',pid), 'bounded profile ID')
    return dict(schema='COMPUTE_METABOLISM_EXECUTION_PROFILE_V1',profile_id=pid,status='CANDIDATE',
        required_cpu_features=list(anchor['required_cpu_features']),environment=dict(cpu_arch='x86_64'),
        libraries={name:dict(sha256=digest,build_id=_build_id(frozen[digest][1]))
            for name,digest in (('libc',libc_hash),('gala',gala_hash),('runtime',runtime_hash))},
        v1_source_binding=anchor['source_binding'],allowed_call_origins=[dict(sha256=h,elf_address=address) for h,address in sorted(origins)],
        entry_points=[anchor['target_entry']],allowed_path=sorted(path),
        expected_inputs=dict(destination='approved_gala_gradient',lengths=list(anchor['lengths']),fill_values=list(anchor['fill_values']),
            domain_status='EXACT_AUDITED_CALL_DOMAIN'),
        memory_contract=dict(reads=['return_address[0:8]'],writes=['destination[0:length]'],
            coverage='INDEPENDENT_V1_COMPLETE_NATIVE_EFFECTS'),
        expected_result=dict(return_value='destination',bytes='exact_fill_byte'),
        allowed_state_changes=sorted(changed),forbidden_state_changes=['outside_destination','unmodelled_registers','callee_saved_registers'],
        verified_capability_rank=anchor['capability_rank'],derived_from=None,verification={})


def _rehash_negative(checkpoint,derived,document,rows):
    from verified_driver.v1.live_chain.checkpoint import chain_hash
    from verified_driver.v1.model import canonical_bytes,content_id
    chain=bytes(32); lines=[]
    for row in rows:
        row.pop('chain',None); chain=hashlib.sha256(chain+_canonical(row)).digest()
        row['chain']=chain.hex(); lines.append(_canonical(row))
    raw=b''.join(lines); event=document['event']; capture=document['metadata']['capture']
    event.update(trace_prefix_bytes=len(raw),trace_prefix_sha256=_sha(raw),trace_chain_hash=chain_hash(raw))
    capture.update(trace_sha256=_sha(raw),final_chain=chain.hex())
    data=canonical_bytes(document); identity=_sha(data)
    (checkpoint/'trace.jsonl').write_bytes(raw); (checkpoint/'checkpoint.json').write_bytes(data)
    (checkpoint/'CHECKPOINT').write_bytes((identity+'\n').encode())
    edge=_json(derived/'edge.json'); edge['checkpoint_id']=identity
    (derived/'edge.json').write_bytes(canonical_bytes(edge))
    done=_json(derived/'completion.json'); done.update(checkpoint_id=identity,edge_sha256=_sha(canonical_bytes(edge)))
    done.pop('completion_sha256'); done['completion_sha256']=content_id(done)
    (derived/'completion.json').write_bytes(canonical_bytes(done))


def _negative_controls(paths,pred,root,anchor):
    """Fresh semantic mutants, fully rehashed; no generated tests confer PASS."""
    from verified_driver.v1.live_chain.checker import check_edge
    from verified_driver.v1.model import canonical_bytes,content_id
    original,derived,_=paths; results=[]
    for mutation in ('unmodelled_instruction','missing_same_value_write','outside_destination_write',
                     'library_identity','caller','entry','forbidden_register','endpoint'):
        with tempfile.TemporaryDirectory(prefix='profile-native-negative-') as temp:
            base=Path(temp); checkpoint=base/'checkpoint'; out=base/'edge'
            shutil.copytree(original,checkpoint); shutil.copytree(derived,out)
            for p in (*checkpoint.iterdir(),*out.iterdir()): p.chmod(0o600)
            document=_json(checkpoint/'checkpoint.json')
            rows=[json.loads(line) for line in _bytes(checkpoint/'trace.jsonl',536870912).splitlines()]
            entry=next(i for i,row in enumerate(rows) if row['elf_address']==anchor['target_entry'])
            store=next(row for row in rows[entry:] if row['possible_memory_writes'])
            if mutation=='unmodelled_instruction': rows[entry]['instruction']='UNKNOWN_NATIVE_OPCODE'
            elif mutation=='missing_same_value_write': store['possible_memory_writes']=[]
            elif mutation=='outside_destination_write': store['possible_memory_writes'][0]['address']+=17
            elif mutation=='library_identity': rows[entry]['module_sha256']='f'*64
            elif mutation=='caller': rows[entry-1]['elf_address']+=1
            elif mutation=='entry': rows[entry]['elf_address']+=1
            elif mutation=='forbidden_register': rows[entry]['post']['gpr']['rbx']='0x0000000000000000'
            if mutation!='endpoint':
                _rehash_negative(checkpoint,out,document,rows)
            else:
                edge=_json(out/'edge.json'); edge['candidate']['q_bits'][0]='0x3ff0000000000000'
                (out/'edge.json').write_bytes(canonical_bytes(edge))
                done=_json(out/'completion.json'); done['edge_sha256']=_sha(canonical_bytes(edge))
                done.pop('completion_sha256'); done['completion_sha256']=content_id(done)
                (out/'completion.json').write_bytes(canonical_bytes(done))
            report=check_edge(checkpoint,out,pred,root)
            _require(report.get('verdict')=='REFUSED' and report.get('failure_stage') in ('RAW','SEMANTIC'),
                'independent semantic negative control did not refuse: '+mutation)
            results.append(dict(mutation=mutation,verdict='REFUSED',failure_stage=report['failure_stage']))
    return results


def _verify_live(paths,anchor_id,root,contract):
    from verified_driver.v1.model import ChainState,chain_genesis,canonical_bytes
    from verified_driver.v1.live_chain.raw import validate_edge
    from verified_driver.v1.live_chain.checker import check_edge
    from verified_driver.v1.live_chain.session import live_source_snapshot
    anchor=REVIEWED_LIVE_ANCHORS[anchor_id]; document,hashes=_authenticate(paths,anchor)
    checkpoint,derived,predecessor=paths
    sources=live_source_snapshot(root)
    _require(sources==document['metadata']['source_snapshot'], 'current V1/source snapshot drift')
    pred=ChainState(**_json(predecessor))
    # Present anchors are first edges. Future non-genesis evidence must include
    # and replay its independently authenticated predecessor chain as well.
    _require(pred.generation==0 and canonical_bytes(pred)==canonical_bytes(chain_genesis(root,pred.requested_steps)),
             'authenticated exact genesis required; non-genesis proof needs predecessor-chain extension')
    doc,event,capture,rows,native,identity=validate_edge(checkpoint,pred,root)
    report=check_edge(checkpoint,derived,pred,root)
    _require(report.get('verdict')=='CHECKER_PASS' and report.get('evidence_role')=='LIVE'
             and report['checkpoint_id']==identity and report['checked_step']==1
             and native['next_body_executed'] is False, 'full independent LIVE checker refused')
    negatives=_negative_controls(paths,pred,root,anchor)
    result=copy.deepcopy(contract); result['status']='VERIFIED'
    result['verification']=dict(authority='INDEPENDENT_PROFILE_GATE_V1',anchor_id=anchor_id,
        independent_verification='FULL_RAW_CHECKPOINT_EDGE_AND_NEGATIVE_REPLAY',
        tests=['full_live_native_recheck','semantic_negative_controls'],evidence_sha256=sorted(hashes.values()),
        proof_files_sha256=hashes,checkpoint_id=identity,completion_sha256=report['completion_sha256'],
        source_binding=anchor['source_binding'],source_count=len(sources),
        profile_gate_sha256=_sha(_bytes(Path(__file__))),raw_effects_rechecked=True,
        negative_controls=negatives,formal_certification=False,numerical_certification=False,
        retained_gaps=copy.deepcopy(doc['metadata'].get('retained_gaps',[])))
    return result


def verify_promotion(candidate_directory):
    """Return VERIFIED only after authenticated independent replay; never write."""
    try:
        directory=_unalias(candidate_directory); root=_unalias(Path(__file__).parents[2])
        candidate=_json(directory/'candidate-profile.json'); proof=_json(directory/'proof-bundle.json')
        allowed={'schema','anchor_id','evidence_role','checkpoint_directory','derived_directory','predecessor','evidence_sha256'}
        _require(set(proof)==allowed and proof['schema']=='COMPUTE_METABOLISM_INDEPENDENT_PROOF_V1'
                 and proof['evidence_role']=='LIVE','explicit independent LIVE proof bundle required; self-issued PASS forbidden')
        _require(candidate.get('status')=='CANDIDATE', 'candidate cannot self-issue VERIFIED')
        anchor_id=proof['anchor_id']; _require(anchor_id in REVIEWED_LIVE_ANCHORS,'independently reviewed authority anchor required')
        anchor=REVIEWED_LIVE_ANCHORS[anchor_id]
        _require(proof['evidence_sha256']==dict(anchor['proof_files_sha256']),'proof file manifest bound to reviewed anchor')
        paths=_paths(directory,proof); _authenticate(paths,anchor)
        contract=_profile_contract(paths,anchor,root,candidate.get('profile_id'))
        _require(set(candidate)==set(contract) and all(candidate[k]==contract[k] for k in contract if k not in ('status','verification')),
                 'candidate library/caller/entry/path/input/effect/result/state/rank/source contract drift')
        _require(candidate['verification'].get('authority') is None
                 and candidate['verification'].get('independent_verification')=='PENDING','candidate authority must remain pending')
        verified=_verify_live(paths,anchor_id,root,contract)
        return dict(promotion_allowed=True,verified_manifest=verified,required_proofs=[],numerical_certification=False)
    except Exception as exc:
        return dict(promotion_allowed=False,required_proofs=[str(exc)],numerical_certification=False)


def existing_historical_profile(repo_root):
    """Recheck the imported original LIVE profile; never infer arbitrary lengths."""
    root=_unalias(repo_root); anchor_id='task8-positive-03-edge-1'; anchor=REVIEWED_LIVE_ANCHORS[anchor_id]
    paths=_anchor_paths(root,anchor); _authenticate(paths,anchor)
    contract=_profile_contract(paths,anchor,root)
    return _verify_live(paths,anchor_id,root,contract)


def verify_registered_profile(profile,repo_root):
    """Registry status/authority labels alone cannot authorize normal execution."""
    root=_unalias(repo_root); _canonical(profile)
    _require(profile.get('status')=='VERIFIED','registered VERIFIED profile required')
    verification=profile.get('verification',{}); anchor_id=verification.get('anchor_id')
    _require(anchor_id in REVIEWED_LIVE_ANCHORS and verification.get('authority')=='INDEPENDENT_PROFILE_GATE_V1',
             'authenticated independent registered authority required')
    anchor=REVIEWED_LIVE_ANCHORS[anchor_id]; paths=_anchor_paths(root,anchor); _authenticate(paths,anchor)
    contract=_profile_contract(paths,anchor,root,profile.get('profile_id'))
    _require(set(profile)==set(contract) and all(profile[k]==contract[k] for k in contract if k not in ('status','verification')),
             'registered contract drift')
    verified=_verify_live(paths,anchor_id,root,contract)
    _require(_canonical(profile)==_canonical(verified),'registered proof/source/gate receipt drift')
    return verified

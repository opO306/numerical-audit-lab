"""Independent new-edge machine/control/memory verification, never an evaluator oracle."""
from collections import Counter
import copy, hashlib, json, re
from pathlib import Path
from verified_driver.v1.model import HARNESS_SHA, content_id, digest_bytes, canonical_bytes, DT
from .protocol import BarrierEvent
from .checkpoint import verify_checkpoint
from runtime_trace.regular_nstep import raw_check as r, machine_check as m
from runtime_trace.regular_2step import structure, checker as body
from runtime_trace.regular_2step.schema import load, canonical

SOURCE_BASE={'runtime_trace/harness.py','runtime_trace/gdb_capture.py','runtime_trace/semantics.py',
 'runtime_trace/regular_2step/acquire.py','runtime_trace/regular_2step/gdb_acquire.py',
 'runtime_trace/caller_transition/gdb_acquire_reads.py','runtime_trace/caller_transition/read_effects.py',
 'runtime_trace/caller_transition/write_effects_reads.py','runtime_trace/caller_transition/write_effects.py',
 'runtime_trace/caller_transition/module_resolver.py','runtime_trace/caller_transition/frozen_modules/manifest.json',
 'runtime_trace/regular_nstep/acquire.py','runtime_trace/regular_nstep/gdb_acquire.py',
 'runtime_trace/regular_nstep/harness.py','runtime_trace/regular_nstep/resources.py',
 'lab/v2_bound.py','independent_checker/oracle.py','runtime_trace/regular_nstep/raw_check.py',
 'runtime_trace/regular_nstep/machine_check.py','runtime_trace/regular_2step/checker.py','runtime_trace/regular_2step/form_oracle.py'}

def _sources(metadata,capture,root):
    pins=metadata['source_snapshot']; expected=set(SOURCE_BASE)
    for folder in ('verified_driver/v1','verified_driver/v1/live_chain'):
        expected.update(p.relative_to(root).as_posix() for p in (root/folder).glob('*.py'))
    r.require(set(pins)==expected and content_id(pins)==metadata['source_binding']==capture['source_pinset_sha256'],'complete source binding')
    for relative,want in pins.items(): r.require(digest_bytes((root/relative).read_bytes())==want,'source snapshot changed: '+relative)
    original=(root/'runtime_trace/harness.py').read_bytes()
    r.require(digest_bytes(original)==HARNESS_SHA,'pinned original harness')
    source=original.decode('utf-8').replace('n_steps=1','n_steps=int(os.environ["RTN_STEPS"])').replace('"n_steps": 1','"n_steps": int(os.environ["RTN_STEPS"])')
    proof={'original_sha256':HARNESS_SHA,'executed_lf_source_sha256':digest_bytes(source.encode()),
      'calculation_replacement':'n_steps=1 -> n_steps=int(os.environ["RTN_STEPS"])',
      'metadata_replacement':'n_steps metadata uses the same requested environment parameter',
      'all_other_source_text_identical':True,'external_gala_modified':False}
    r.require(capture['harness_source_proof']==proof,'executed original source contract')

def _context(context):
    result=dict(context)
    # The body collector declares an empty optional vector map; the caller
    # collector omits it. Nonempty additional lanes remain part of the seam.
    if result.get('extra_vectors')=={}: result.pop('extra_vectors')
    return result

def _past_shadow(rows,start):
    # The previous certified bytes are hash-bound. Restore their memory effects,
    # without recomputing previously accepted numerical/IR/Form operations.
    shadow={}
    for original in rows[start:]:
        row=m.normalized(original)
        for o in row['pre_memory_observations']:
            for i,b in enumerate(bytes.fromhex(o['bytes_hex'])): shadow[o['address']+i]=b
        for w in row['possible_memory_writes']:
            for i,b in enumerate(int(w['after_bits'],16).to_bytes(w['size'],'little')): shadow[w['address']+i]=b
    return shadow

def validate_edge(checkpoint,pred,root):
    checkpoint=Path(checkpoint); root=Path(root)
    doc=verify_checkpoint(checkpoint); event=BarrierEvent(**doc['event']); metadata=doc['metadata']; capture=metadata['capture']
    r.require(event.completed_step==pred.step_index+1 and event.predecessor_id==pred.content_hash and event.requested_steps==pred.requested_steps,'immediate certified predecessor/step')
    r.require(pred.barrier_kind!='FINAL_TERMINAL','terminal predecessor cannot authorize a body')
    snap=event.checkpoint_state; k=event.completed_step
    r.require(capture['schema']=='gala-live-prefix-v1' and capture['verdict']=='PAUSED','live prefix capture required')
    r.require(capture['wheel_sha256']=='cc5f0cf3bc63a966a3c130b93f6c05026271fe7178492a02c6266c243b5fc2f0' and capture['machine_mapping_read_by_tracer'] is False,'original wheel/acquisition contract')
    r.require(capture['requested_steps']==event.requested_steps and capture['process_identity']==dict(event.process_identity) and capture['acquisition_id']==event.session_id,'strict live process/session binding')
    _sources(metadata,capture,root)
    if pred.generation:
        r.require(pred.live_session_id==event.session_id and pred.process_identity_digest==content_id(event.process_identity) and pred.source_binding==metadata['source_binding'],'foreign live predecessor/session/source')
    raw=(checkpoint/'trace.jsonl').read_bytes()
    r.require(len(raw)<=536870912,'raw prefix ceiling')
    if pred.generation: r.require(digest_bytes(raw[:pred.trace_prefix_bytes])==pred.trace_prefix_sha256,'certified prefix mutation')
    rows=[]; chain='0'*64
    for line in raw.splitlines():
        row=json.loads(line,object_pairs_hook=body._pairs if hasattr(body,'_pairs') else __import__('runtime_trace.regular_2step.schema',fromlist=['_pairs'])._pairs,
          parse_constant=lambda v: (_ for _ in ()).throw(ValueError('nonfinite raw JSON')))
        chain=hashlib.sha256(bytes.fromhex(chain)+canonical({a:b for a,b in row.items() if a!='chain'})).hexdigest()
        r.require(row['chain']==chain,'raw global chain/order'); rows.append(row)
    r.require(chain==capture['final_chain'] and capture['trace_sha256']==event.trace_prefix_sha256,'prefix acquisition identity')
    r._numeric_types(capture); r._numeric_types(rows)
    r.require(len(rows)==capture['record_count'] and [x['seq'] for x in rows]==list(range(len(rows))),'dense unique prefix sequence')
    histogram=Counter(row.get('opcode') or row['assembly'].split()[0] for row in rows)
    r.require(all(type(v) is int and v>0 for v in capture['opcode_histogram'].values()) and dict(histogram)==capture['opcode_histogram'],'exact prefix opcode histogram')
    r.require(capture['scalar_fp_count']==sum(row.get('kind') in ('ADD','SUB','MUL') for row in rows),'exact prefix scalar operation count')
    r.require(snap['frontier']==len(rows)-1 and snap['body_count']==k,'exact checkpoint frontier/body count')
    regions=capture['regions']; corridors=capture['caller_corridors']
    r.require([x['occurrence'] for x in regions]==['init']+[f'step{i}' for i in range(1,k+1)],'no missing/extra/early next body')
    region=regions[-1]; start=0 if k==1 else pred.verified_frontier+1
    r.require(region['start_seq']==(regions[0]['end_seq'] if k==1 else start),'new body exactly at prior frontier')
    r.require(region['start_state']['q']==list(pred.q_bits) and region['start_state']['full_v']==list(pred.full_v_bits) and region['start_state']['latent']==list(pred.latent_bits),'certified q/full_v/latent exact handoff')
    r.require(region['start_state']['gradient']==list(pred.gradient_bits) and region['dt_bits']==DT,'entry gradient/dt contract')
    if k>1: r.require(region['t_bits']==pred.next_t_bits,'certified next t entry')
    if event.barrier_kind=='NEXT_STEP_ENTRY':
        r.require(capture['terminal_corridor'] is None and len(corridors)==k,'nonterminal corridor count')
        corridor=corridors[-1]; following=json.loads(canonical_bytes(snap['next_entry'])); following['occurrence']=f'step{k+1}'
        r.require('end_seq' not in following and 'end_state' not in following,'no executed successor snapshot')
        r.require(corridor['occurrence']==f'caller{k}-{k+1}' and corridor['start_seq']==region['end_seq'] and corridor['end_seq']==len(rows),'body/caller complete prefix coverage')
        r.require(following['entry_pc']==snap['paused_pc']==r._pc(rows[-1])[1] and _context(following['context'])==_context(rows[-1]['post']),'actual stopped entry PC/context')
        for name in ('q','full_v','latent','gradient'): r.require(list(snap[name])==following['start_state'][name],'checkpoint entry component snapshot')
        r.require(snap['t_bits']==following['t_bits'] and snap['dt_bits']==following['dt_bits'],'checkpoint represented t/dt')
        spans=([regions[0]] if k==1 else [])+[region,corridor]
    else:
        terminal=capture['terminal_corridor']
        r.require(snap['next_entry'] is None and snap['t_bits'] is None and len(corridors)==k-1,'terminal forbids successor data')
        r.require(terminal is not None and terminal['occurrence']==f'terminal{k}' and terminal['start_seq']==region['end_seq'] and terminal['end_seq']==len(rows),'complete native terminal corridor')
        r.require(snap['paused_pc']==r._pc(rows[-1])[1],'actual terminal paused frontier')
        for name in ('q','full_v','latent'): r.require(list(snap[name])==region['end_state'][name],'terminal logical lanes')
        r.require(list(snap['gradient'])==region['start_state']['gradient'] and snap['dt_bits']==region['dt_bits'],'terminal retains last observed entry gradient/dt rule')
        spans=([regions[0]] if k==1 else [])+[region,terminal]
    r.require(spans[0]['start_seq']==start and spans[-1]['end_seq']==len(rows),'new edge coverage')
    for span in spans:
        r.require(span['start_seq']<span['end_seq'] and all(x['occurrence']==span['occurrence'] for x in rows[span['start_seq']:span['end_seq']]),'new edge occurrence/order')
    identity=capture['process_identity']; pid=identity['pid']; owner=regions[0]['ptid']
    r.require(set(identity)=={'pid','linux_boot_id','proc_stat_start_time_ticks'} and type(pid) is int and pid>0 and identity['proc_stat_start_time_ticks']>0,'structured live process birth')
    r.require(re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',identity['linux_boot_id']) is not None and owner[0]==pid and owner[1]>0 and owner[2]==0,'live birth/thread identity')
    new=rows[start:]
    for row in new:
        r.require(row['pid']==pid and row['ptid']==owner and row.get('thread_ptid',owner)==owner,'cross-process/thread row splice')
        for c in (row['pre'],row['post']):
            r.require(c['mxcsr']&((3<<13)|(1<<15)|(1<<6))==0 and c['mxcsr']&0x1f80==0x1f80,'supported rounding environment')
    for index in range(max(1,start),len(rows)):
        if k==1 and index==regions[1]['start_seq']: continue # retained sole inherited gap
        before,after=rows[index-1],rows[index]
        r.require(r._pc(before)[1]==r._pc(after)[0] and _context(before['post'])==_context(after['pre']),'complete PC/register seam')
    for current in ([regions[0],region] if k==1 else [region]):
        r.require(current['entry_pc']==r._pc(rows[current['start_seq']])[0] and current['return_pc']==r._pc(rows[current['end_seq']-1])[1] and current['ptid']==owner and current['scheduler_locking']=='Mode for locking scheduler during execution is "on".','all-stop actual body entry/return')
    decoded=r._decoded(new,root,capture['modules'])
    native=[m.normalized(row) for row in new]
    native_decode={row['seq']:m.effect_assembly(decoded[row['module_sha256'],row['elf_address']][1]) for row in new}
    gap=regions[1]['start_seq']
    if k==1:
        r._memory(native[:gap],native_decode); r._memory(native[gap:],native_decode)
    else:
        shadow=_past_shadow(rows[:start],gap)
        for name in ('q','full_v','latent','gradient'):
            for offset,value in zip((0,8),getattr(pred,name+'_bits')):
                for i,b in enumerate(int(value,16).to_bytes(8,'little')):
                    address=region['pointers'][name]+offset+i
                    r.require(address in shadow and shadow[address]==b,'previous certified memory/continuation seed')
        r._memory(native,native_decode,shadow)
    bases={module['sha256']:module['load_base'] for module in capture['modules'].values()}
    m.registers(native,native_decode); m.controls(native,native_decode,bases); m.writes(native,native_decode)
    structure._check_observations([x for current in ([regions[0],region] if k==1 else [region]) for x in rows[current['start_seq']:current['end_seq']]])
    old=load(root/'runtime_trace/regular_2step/artifacts/known-03/capture.json'); oldrows,_=structure._load_rows(root/'runtime_trace/regular_2step/artifacts/known-03/trace.jsonl')
    oldstep=old['regions'][1]
    r.require(r._base_structure(rows[region['start_seq']:region['end_seq']],region,capture['modules'])==r._base_structure(oldrows[oldstep['start_seq']:oldstep['end_seq']],oldstep,old['modules']),'audited step topology/module-relative control')
    if k>1:
        first=regions[1]
        structure.compare_step_structures(rows[first['start_seq']:first['end_seq']],rows[region['start_seq']:region['end_seq']],first,region)
    if k==1:
        ops,values,_=body.graph(capture,rows[:regions[1]['end_seq']],regions[:2],root,prefix=True)
        ir=load(root/'runtime_trace/numeric_ir/artifacts/attempt-05/numeric_ir.json')
        r.require(ops==ir['operations'] and values==ir['values'],'audited init/step1 base graph/bits')
        for fresh,prior in zip(regions[:2],old['regions'][:2]):
            r.require(r._base_structure(rows[fresh['start_seq']:fresh['end_seq']],fresh,capture['modules'])==r._base_structure(oldrows[prior['start_seq']:prior['end_seq']],prior,old['modules']),'audited base topology')
    allowed=r._closed_caller_sites(root)
    if event.barrier_kind=='NEXT_STEP_ENTRY':
        joined=r._caller_join(region,following,corridor,rows[corridor['start_seq']:],decoded,capture['modules'],allowed)
        stores=r._output_stores(region,rows[corridor['start_seq']:],decoded,event.requested_steps)
        if k>1: r.require(corridor['argument_sources']['t']['source_memory_address']==corridors[0]['argument_sources']['t']['source_memory_address']+8*(k-1),'contiguous step schedule provenance')
        native_report={'kind':event.barrier_kind,'join':joined,'output_stores':stores,'next_body_executed':False}
    else:
        native_report={'kind':event.barrier_kind,'terminal_output_stores':r._terminal(capture,rows,decoded,allowed),'next_body_executed':False}
    native_report.update(step_index=k,last_verified_trace_seq=len(rows)-1,new_start_seq=start,new_record_count=len(new))
    identity=(checkpoint/'CHECKPOINT').read_text().strip()
    return doc,event,capture,rows,native_report,identity

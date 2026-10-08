"""GDB-only actual Gala CALL→PLT/GOT→finite EVEX path recorder.

No certified store is read or created. Kill at the first approved memset return;
do not execute the following Gala instruction or any certification barrier.
"""
import hashlib,json,os,sys,time
from copy import deepcopy
from pathlib import Path
import gdb

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from compute_metabolism.v0.adaptive import canonical,elf_build_id
from compute_metabolism.v0.gala_observer import elf_load_bias,write_bounded,validate_reservation,STATE_LIMIT
from verified_driver.v1.model import content_id
from verified_driver.v1.native_evex_capture import collect_state,observe_control
from verified_driver.v1.native_evex_collector import record_step,PATH

class ModuleNotLoaded(ValueError):pass


def memory(address,size):return bytes(gdb.selected_inferior().read_memory(address,size))


def record_caller(state,memory,step,call_pc,plt_pc,got,result):
    before=state();result['last_before']=before;result['last_after']=None
    attempt=dict(before=deepcopy(before),after_call=None,entry=None,stack_write=None,got_bytes_hex=None)
    result['attempted_caller']=attempt
    if before['registers']['rsi']!=0 or before['registers']['rdx']!=16:
        raise ValueError('actual Gala CALL input outside finite zero16 domain')
    if memory(call_pc,5).hex()!='e8c20cfdff':raise ValueError('actual CALL bytes drift')
    rsp=before['registers']['rsp'];stack_before=memory(rsp-8,8)
    attempt['stack_write']=dict(address=rsp-8,size=8,before_hex=stack_before.hex(),after_hex=None)
    attempt['stage']='execute-CALL';step()
    attempt['stage']='collect-CALL-post';after_call=state()
    attempt['after_call']=deepcopy(after_call);result['last_after']=after_call
    stack_after=memory(rsp-8,8);attempt['stack_write']['after_hex']=stack_after.hex()
    if after_call['registers']['rip']!=plt_pc or memory(plt_pc,6).hex()!='ff253aae0300':
        raise ValueError('actual approved PLT path drift')
    got_raw=memory(got,8);attempt['got_bytes_hex']=got_raw.hex()
    result['last_before']=after_call;result['last_after']=None
    attempt['stage']='execute-PLT';step()
    attempt['stage']='collect-PLT-post';entry=state()
    attempt['entry']=deepcopy(entry);result['last_after']=entry
    return before,after_call,entry,stack_before,stack_after,got_raw


def record_native(state,memory,step,load_base,result):
    native=result['native'];result['enabled_write_observations']=[]
    for index,(pc,code) in enumerate(PATH):
        result['stage']='native-instruction-'+str(index)
        result['last_after']=None
        current=state();result['last_before']=current
        if current['registers']['rip']!=load_base+pc or memory(load_base+pc,len(code)//2).hex()!=code:
            raise ValueError('actual finite path PC/code drift')
        row=record_step(pc,code,current,memory,step,state,load_base)
        result['last_after']=row['after']
        result['enabled_write_observations'].extend(deepcopy(row.pop('write_observations')))
        row.pop('defined_flags_mask');native['steps'].append(row)
    native['exit']=state()


def mapped_module(path,pid):
    path=Path(path).resolve(strict=True);matches=[]
    for line in Path('/proc/'+str(pid)+'/maps').read_text().splitlines():
        fields=line.split(maxsplit=5)
        if len(fields)==6 and fields[5]==str(path):
            start,end=(int(x,16) for x in fields[0].split('-'))
            matches.append(dict(start=start,end=end,offset=int(fields[2],16),perms=fields[1]))
    if not matches:raise ModuleNotLoaded('pinned module not mapped')
    raw=path.read_bytes()
    return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),
        build_id=elf_build_id(raw),load_base=elf_load_bias(raw,matches),segments=matches)


def run(config,result):
    fp=config['fingerprint'];started=time.monotonic()
    result['stage']='prepared-GDB-and-source'
    validate_reservation(config['writer_reservation'])
    if (config['max_native_steps']!=13 or config['stop_at']!='FIRST_APPROVED_MEMSET_RETURN'
        or config['mode']!='OBSERVATION' or config['certified_state_progress'] is not False):
        raise ValueError('fixed noncertified observation contract')
    for path,want in config['source_snapshot'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest()!=want:
            raise ValueError('source changed before acquisition: '+path)
    if hashlib.sha256(Path('/usr/bin/gdb').read_bytes()).hexdigest()!=config['gdb_sha256']:
        raise ValueError('prepared GDB drift')
    for command in ('set pagination off','set confirm off','set print thread-events off',
        'set non-stop off','set startup-with-shell off','set disassembly-flavor intel',
        'set stop-on-solib-events 1','set disable-randomization off'):
        gdb.execute(command,to_string=True)
    result['stage']='CPUID'
    control,witness=observe_control()
    gdb.execute('starti',to_string=True)
    pid=gdb.selected_inferior().pid
    stat=Path('/proc/'+str(pid)+'/stat').read_text().rsplit(')',1)[1].split()
    birth=dict(pid=pid,linux_boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        proc_stat_start_time_ticks=int(stat[19]))
    write_bounded(config['candidate_birth'],canonical(dict(pid=pid)),65536)
    # Parent independently binds /proc birth, GDB ancestry, runtime and cgroup.
    wait_deadline=time.monotonic()+5
    while not Path(config['birth']).is_file():
        if time.monotonic()>wait_deadline:raise ValueError('independent parent birth proof unavailable')
        time.sleep(.01)
    if json.loads(Path(config['birth']).read_bytes())!=birth:
        raise ValueError('parent/inferior birth seam mismatch')
    result['stage']='Gala-module-load'
    for _ in range(4096):
        if time.monotonic()-started>config['timeout_seconds']:raise ValueError('bounded module-load deadline')
        try:gala=mapped_module(fp['gala']['path'],pid);break
        except ModuleNotLoaded:gdb.execute('continue',to_string=True)
    else:raise ValueError('Gala module load event limit')
    if gala['sha256']!=fp['gala']['sha256'] or gala['build_id']!=fp['gala']['build_id']:
        raise ValueError('mapped Gala identity drift')
    libc=mapped_module(fp['libc']['path'],pid)
    if libc['sha256']!=fp['libc']['sha256'] or libc['build_id']!=fp['libc']['build_id']:
        raise ValueError('mapped libc identity drift')
    if hashlib.sha256(Path('/proc/'+str(pid)+'/exe').resolve(strict=True).read_bytes()).hexdigest()!=fp['runtime']['sha256']:
        raise ValueError('actual inferior runtime drift')
    gdb.execute('set stop-on-solib-events 0',to_string=True)
    call_pc=gala['load_base']+0x35689
    breakpoint=gdb.Breakpoint('*'+hex(call_pc),internal=True)
    result['stage']='approved-Gala-CALL'
    gdb.execute('continue',to_string=True);breakpoint.enabled=False
    if int(gdb.newest_frame().read_register('rip'))!=call_pc:raise ValueError('approved CALL not reached')
    owner=list(gdb.selected_thread().ptid);gdb.execute('set scheduler-locking on',to_string=True)
    state_acquisitions=[]
    def state():
        if len(state_acquisitions)>=64:raise ValueError('bounded Gala state acquisition evidence limit')
        evidence={}
        context=collect_state(gdb.newest_frame(),control,raw_evidence=evidence)
        state_acquisitions.append(dict(sample_index=len(state_acquisitions),context_rip=context['registers']['rip'],context_sha256=hashlib.sha256(canonical(context)).hexdigest(),evidence=deepcopy(evidence)))
        result['state_acquisitions']=state_acquisitions
        return context
    def step():
        if list(gdb.selected_thread().ptid)!=owner or gdb.selected_inferior().pid!=pid:
            raise ValueError('inferior/thread drift before stepi')
        gdb.execute('stepi',to_string=True)
        if list(gdb.selected_thread().ptid)!=owner or gdb.selected_inferior().pid!=pid:
            raise ValueError('inferior/thread drift after stepi')
    plt_pc=gala['load_base']+0x6350;got=gala['load_base']+0x41190
    before,after_call,entry,stack_before,stack_after,got_raw=record_caller(state,memory,step,call_pc,plt_pc,got,result)
    rsp=before['registers']['rsp']
    if entry['registers']['rip']!=libc['load_base']+0x1996c0:
        raise ValueError('actual libc entry outside finite verified candidate path')
    caller=dict(path=gala['path'],sha256=gala['sha256'],build_id=gala['build_id'],load_base=gala['load_base'],
        elf_pc=0x35689,instruction_bytes='e8c20cfdff',return_pc=call_pc+5,plt_elf_pc=0x6350,
        plt_instruction_bytes='ff253aae0300',got_elf_address=0x41190,got_address=got,got_bytes_hex=got_raw.hex(),
        before=before,after_call=after_call,entry=entry,stack_write=dict(address=rsp-8,size=8,
            before_hex=stack_before.hex(),after_hex=stack_after.hex()))
    domain=dict(provenance_kind='ACTUAL_GALA_CALL',source_sha256=content_id(config['source_snapshot']),
        caller_module_sha256=gala['sha256'],caller_elf_pc=0x35689,caller_instruction_bytes='e8c20cfdff',
        caller_return_pc=call_pc+5,caller_load_base=gala['load_base'],caller_path=gala['path'],caller_build_id=gala['build_id'],
        destination=before['registers']['rdi'],length=16,fill=0,libc_sha256=libc['sha256'],libc_build_id=libc['build_id'])
    native=dict(schema='native-evex-trace-v1',library={k:libc[k] for k in ('sha256','build_id')},
        load_base=libc['load_base'],domain=domain,entry=entry,exit=None,steps=[])
    result.update(caller=caller,native=native)
    record_native(state,memory,step,libc['load_base'],result)
    if native['exit']['registers']['rip']!=call_pc+5:raise ValueError('actual return target drift')
    # Kill while paused at CALL return. The next Gala instruction is never run.
    result['stage']='kill-before-certification'
    gdb.execute('kill',to_string=True)
    if gdb.selected_inferior().pid!=0 or Path('/proc/'+str(pid)).exists():
        raise ValueError('owned inferior remains after kill')
    writes=deepcopy(result['enabled_write_observations'])
    write_bounded(Path(config['result']).with_name('enabled-write-observations.json'),canonical(writes),524288)
    seal_observation(result,config,fp,birth,owner,witness,caller,native,state_acquisitions)


def seal_observation(result,config,fp,birth,owner,witness,caller,native,samples):
    # Separate bounded raw evidence preserves the strict origin document schema.
    result.clear();result.update(schema='gala-native-observation-v1',source_snapshot=config['source_snapshot'],
        source_binding=content_id(config['source_snapshot']),fingerprint=fp,process_identity=birth,thread_ptid=owner,
        control_witness=witness,caller=caller,native=native,
        termination=dict(inferior_killed=True,remaining_owned_pids=[],certified_state_progress=False))
    sidecar=dict(schema='gala-state-acquisitions-v2',observation_sha256=hashlib.sha256(canonical(result)).hexdigest(),
        observer_config_sha256=hashlib.sha256(canonical(config)).hexdigest(),source_binding=result['source_binding'],
        process_identity=deepcopy(birth),thread_ptid=deepcopy(owner),gdb_sha256=config['gdb_sha256'],samples=deepcopy(samples))
    write_bounded(Path(config['result']).with_name('state-acquisitions.json'),canonical(sidecar),STATE_LIMIT)


def main():
    config=json.loads(Path(os.environ['CM_GALA_OBSERVER_CONFIG']).read_bytes());result={}
    try:run(config,result)
    except Exception as exc:
        if hasattr(exc,'diagnostic_receipt'):
            key='control_failure' if 'leaf0' in exc.diagnostic_receipt else 'failed_step'
            result[key]=deepcopy(exc.diagnostic_receipt)
            if key=='failed_step':result['last_after']=exc.diagnostic_receipt.get('after')
        result['diagnostic']=dict(stage=result.get('stage','startup'),exception_type=type(exc).__name__,exception_message=str(exc))
    finally:
        if gdb.selected_inferior().pid:
            try:gdb.execute('kill',to_string=True)
            except Exception as exc:result['cleanup_diagnostic']=str(exc)
        writes=Path(config['result']).with_name('enabled-write-observations.json')
        if not writes.exists():
            write_bounded(writes,canonical(result.get('enabled_write_observations',[])),524288)
        state_file=Path(config['result']).with_name('state-acquisitions.json')
        samples=result.pop('state_acquisitions',[])
        if not state_file.exists():
            write_bounded(state_file,canonical(dict(schema='gala-state-acquisitions-v1',samples=samples)),STATE_LIMIT)
        write_bounded(config['result'],canonical(result),config['max_output_bytes'])
    if 'diagnostic' in result:raise RuntimeError(json.dumps(result['diagnostic'],sort_keys=True))

main()

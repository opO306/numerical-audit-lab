"""Actual Gala Task8 experiments; exclusive evidence; production numerics/gate."""
from pathlib import Path
from dataclasses import asdict
import argparse,hashlib,json,os,signal,subprocess,sys,time,shutil
ROOT=Path.cwd();sys.path.insert(0,str(ROOT));BASE=ROOT/'verified_driver/v1/artifacts/task8'
from verified_driver.v1.model import chain_genesis,canonical_bytes,content_id,digest_bytes,strict_json
from verified_driver.v1.store import ChainStore
from verified_driver.v1.controller import VerifiedChainDriver
from verified_driver.v1.gate import V1Gate
from verified_driver.v1.replay import ReplayEngine
from verified_driver.v1.live_chain.session import LiveGalaSession,live_source_snapshot
from verified_driver.v1.live_chain.checkpoint import sealed_write,verify_checkpoint
LEDGER=Path(os.environ['GIT_WORK_TREE'])/'runtime_trace/regular_nstep/artifacts/budget.json'
SCRIPT=Path(__file__).resolve()

def save(path,doc):sealed_write(path,canonical_bytes(doc))
def load(path):return strict_json(path.read_bytes())
def files(root):return {p.relative_to(root).as_posix():digest_bytes(p.read_bytes()) for p in root.rglob('*') if p.is_file() and p.name!='.lock'}
def markers(root):return sorted(int(p.stem.rsplit('-',1)[1]) for p in root.glob('body-start-*.json'))
def until(predicate,seconds):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        if predicate():return
        time.sleep(.002)
    raise TimeoutError('required actual Gala evidence did not arrive')

class ObservedSession(LiveGalaSession):
    def __init__(self,*args,store,allow_replay=False,**kwargs):
        super().__init__(*args,**kwargs);self.store=store;self.allow_replay=allow_replay
    def _receive(self,*args):
        event=super()._receive(*args)
        save(self.run_root/f'observed-barrier-{event.completed_step}.json',{'event':asdict(event),'paused_proved':self.is_paused_at(event),'markers':markers(self.run_root),'monotonic_ns':time.monotonic_ns()})
        return event
    def resume(self,token):
        current,state=self.store.recover();k=token.barrier_seq
        assert token.state_id==current or self.allow_replay and any(s.content_hash==token.state_id for s in self.store.chain())
        assert not (self.run_root/f'body-start-{k+1}.json').exists()
        save(self.run_root/f'observed-resume-{k}.json',{'token':asdict(token),'CURRENT':current,'current_generation':state.generation,'next_body_absent':True,'replay_ancestor_only':token.state_id!=current,'monotonic_ns':time.monotonic_ns()})
        return super().resume(token)

def driver(store,out,*,replay=False,gate=None):
    d=VerifiedChainDriver(ROOT,store,out/'runs',LEDGER);d._gate=gate or V1Gate()
    d._make_session=lambda *args:ObservedSession(*args,store=store,allow_replay=replay)
    def publication(point):
        if point=='after_current_replace':
            e=d.session.event;k=e.completed_step
            assert markers(d.session.run_root)==list(range(1,k+1))
            assert d.session.is_paused_at(e)
            save(out/f'publication-{k}.json',{'CURRENT':(store.root/'CURRENT').read_text().strip(),'step':k,'markers':markers(d.session.run_root),'paused_proved':True,'next_body_absent':not (d.session.run_root/f'body-start-{k+1}.json').exists(),'monotonic_ns':time.monotonic_ns()})
    store._crash_hook=publication
    return d

class NegativeGate(V1Gate):
    def _worker(self,mode,cp,pred_path,out,root,report):
        super()._worker(mode,cp,pred_path,out,root,report)
        if mode=='produce' and load(cp/'checkpoint.json')['event']['completed_step']==3:
            edge=load(out/'edge.json');before=digest_bytes((out/'edge.json').read_bytes())
            edge['candidate']['forms'][0]['box']='0x1.0000000000000p+0'
            (out/'edge.json').write_bytes(canonical_bytes(edge));done=load(out/'completion.json')
            done['edge_sha256']=digest_bytes((out/'edge.json').read_bytes());done.pop('completion_sha256');done['completion_sha256']=content_id(done)
            (out/'completion.json').write_bytes(canonical_bytes(done))
            save(out.with_name(out.name+'.intentional-negative.json'),{'step':3,'mutation':'candidate Form box changed; outer edge/completion hashes repaired','edge_before':before,'edge_after':done['edge_sha256'],'checkpoint_unchanged':True,'historical_S1_S2_unchanged':True})

def run_control(out):
    env=dict(os.environ,RT_OUTPUT=str(out),RTN_STEPS='3',LD_BIND_NOW='1')
    subprocess.run([sys.executable,str(ROOT/'runtime_trace/regular_nstep/harness.py')],cwd=ROOT,env=env,check=True)
    result=load(out/'harness_output.json');assert result['n_steps']==3
    return {'verdict':'PASS','public_bits':result['output_bits'],'scope':'ordinary original Gala N3 public output only'}

def run_live(out,n,negative):
    store=ChainStore(out/'store');store.initialize(chain_genesis(ROOT,n))
    d=driver(store,out,gate=NegativeGate() if negative else None);result=d.run(n,'actual')
    save(out/'controller-result.json',asdict(result));save(out/'metrics.json',d.metrics)
    live=d.session.run_root if d.session else out/'runs/actual/live'
    expected='STOP' if negative else 'ACCEPT';generation=2 if negative else 3
    assert result.verdict==expected and result.generation==store.recover()[1].generation==generation,result
    assert markers(live)==[1,2,3] and not (live/'body-start-4.json').exists()
    chain=store.chain();assert len(chain)==generation+1
    pids={load(live/f'body-start-{k}.json')['pid'] for k in (1,2,3)};assert len(pids)==1
    if negative:
        assert load(out/'runs/actual/edge-3.checker.json')['verdict']=='REFUSED'
        assert store.current()[0]==chain[2].content_hash and d.session._phase=='STOPPED'
    else:
        assert chain[-1].barrier_kind=='FINAL_TERMINAL' and d.session._phase=='FINISHED'
        assert list(chain[-1].public_bits)==load(BASE/'ordinary-01/harness_output.json')['output_bits']
    return {'verdict':'PASS','observed_result':asdict(result),'CURRENT':store.current()[0],
      'generations':[s.content_hash for s in chain],'markers':markers(live),'one_inferior_pid':list(pids)[0],
      'session':d.session.session_id,'source_binding':chain[1].source_binding,'public_bits':list(chain[-1].public_bits),
      'body4_absent':True,'evidence_role':'LIVE','formal_certification':False}

def run_replay(out,terminal,positive_ref,negative_ref):
    original=BASE/(positive_ref if terminal else negative_ref);store=ChainStore(original/'store')
    before=files(store.root);historical=store.chain();target=historical[-1];old=target.content_hash
    replay_checks=[]
    class ObservedGate(V1Gate):
        def observe(self,*args):
            cp=args[1];k=load(cp/'checkpoint.json')['event']['completed_step']
            report=super().observe(*args)
            if k<=target.generation:
                assert files(store.root)==before and store.recover()[0]==old
                replay_checks.append({'step':k,'CURRENT':old,'store_bytes_unchanged':True,'report_sha256':content_id(report)})
            return report
    d=driver(store,out,replay=True,gate=ObservedGate())
    result=ReplayEngine(lambda:d,store).recover(target.requested_steps,'actual-replay')
    save(out/'controller-result.json',asdict(result));save(out/'metrics.json',d.metrics);save(out/'replay-store-checks.json',replay_checks)
    assert result.verdict=='ACCEPT',result
    assert len(replay_checks)==target.generation
    live=d.session.run_root
    if terminal:
        assert files(store.root)==before and result.state_id==old and markers(live)==[1,2,3]
        assert not (live/'body-start-4.json').exists()
    else:
        for name,digest in before.items():
            if name!='CURRENT':assert digest_bytes((store.root/name).read_bytes())==digest
        chain=store.chain();assert result.generation==4 and chain[3].predecessor_id==old
        r3=load(store.root/'receipts'/(chain[3].acceptance_id+'.json'));r4=load(store.root/'receipts'/(chain[4].acceptance_id+'.json'))
        tid=r3['replay_transition_id'];assert 'replay_transition_id' not in r4
        attachment=load(store.root/'replay_transitions'/(tid+'.json'));assert attachment['historical_state_id']==old
        assert markers(live)==[1,2,3,4]
    assert d.session.session_id!=target.live_session_id
    from runtime_trace.regular_nstep.resources import reserve_writer
    reserve_writer(sum(p.stat().st_size for p in store.root.rglob('*') if p.is_file()))
    shutil.copytree(store.root,out/'result-store')
    return {'verdict':'PASS','evidence_role':'LIVE','historical_target':old,'result':asdict(result),
       'historical_objects_receipts_unchanged':True,'publication_during_replay':False,'replay_checks':replay_checks,
       'fresh_session':d.session.session_id,'markers':markers(live),'terminal_replay':terminal,'formal_certification':False}

def child(out,mode):
    store=ChainStore(out/'store');store.initialize(chain_genesis(ROOT,3))
    if mode=='interruption':
        d=driver(store,out)
        def interrupt(point):
            if point=='after_current_replace_before_token':
                save(out/'interrupted.json',{'CURRENT':store.recover()[0],'generation':1,'markers':markers(d.session.run_root),'before_token':True,'controller_pid':os.getpid()})
                os._exit(75)
        d._crash_hook=interrupt;d.run(3,'actual');raise AssertionError('interruption did not occur')
    s=LiveGalaSession(ROOT,out/'live',3,LEDGER)
    save(out/'controller-ready.json',{'pid':os.getpid(),'mode':mode,'session_id':s.session_id})
    event=s.start()
    assert s.is_paused_at(event)
    save(out/'paused.json',{'event':asdict(event),'CURRENT':store.recover()[0],'generation':0,'paused_proved':True})
    while True:time.sleep(.05)

def tail_row(path):
    with path.open('rb') as f:
        f.seek(0,2);size=f.tell();f.seek(max(0,size-262144));raw=f.read()
    lines=raw.splitlines()
    for line in reversed(lines[:-1] if raw[-1:]!=b'\n' else lines):
        try:return json.loads(line)
        except ValueError:pass
    return None

def run_death(out,active):
    mode='active' if active else 'paused'
    controller=subprocess.Popen([sys.executable,str(SCRIPT),'child',str(out),mode],cwd=ROOT)
    try:
        live=out/'live'
        if active:
            def in_body():
                p=live/'body-start-1.json'
                if not p.exists() or (out/'paused.json').exists() or (live/'metadata-1.json').exists():return False
                row=tail_row(live/'trace.jsonl');return row is not None and row['seq']>=load(p)['trace_start_seq']
            until(in_body,12);row=tail_row(live/'trace.jsonl')
            observed={'active_body_started':load(live/'body-start-1.json'),'last_complete_trace_row':row,'barrier_metadata_absent':not (live/'metadata-1.json').exists()}
            assert observed['barrier_metadata_absent']
        else:
            until(lambda:(out/'paused.json').exists(),12);observed=load(out/'paused.json')
        inferior=load(live/'body-start-1.json')['pid']
        observed.update(inferior_pid=inferior,inferior_pgid=os.getpgid(inferior),controller_pid=controller.pid)
        save(out/'before-controller-death.json',observed)
        os.kill(controller.pid,signal.SIGKILL);controller.wait(timeout=2)
        until(lambda:(live/'containment.json').exists(),2)
        receipt=load(live/'containment.json')
        assert receipt['reason']=='CONTROLLER_PIPE_EOF' and receipt['group_remaining_pids']==[]
        until(lambda:not Path('/proc',str(inferior)).exists(),1)
        assert markers(live)==[1] and not (live/'body-start-2.json').exists()
        store=ChainStore(out/'store');assert store.recover()[1].generation==0
        return {'verdict':'PASS','evidence_role':'LIVE','mode':mode,'CURRENT':store.current()[0],'generation':0,
           'markers':[1],'inferior_pid':inferior,'inferior_absent_after_death':True,'containment':receipt,
           'active_observation':observed if active else None,'formal_certification':False}
    finally:
        if controller.poll() is None:controller.kill();controller.wait(timeout=2)

def run_interruption(out):
    controller=subprocess.Popen([sys.executable,str(SCRIPT),'child',str(out),'interruption'],cwd=ROOT)
    code=controller.wait(timeout=22);assert code==75
    live=out/'runs/actual/live';until(lambda:(live/'containment.json').exists(),2)
    store=ChainStore(out/'store');sid,state=store.recover();assert state.generation==1
    report=load(out/'runs/actual/edge-1.checker.json');receipt=load(store.root/'receipts'/(state.acceptance_id+'.json'))
    assert receipt['checker_report_sha256']==content_id(report)
    cp=out/'runs/actual/checkpoint-1';verify_checkpoint(cp,receipt['checkpoint_id'])
    from verified_driver.v1.live_chain.checker import check_edge
    checked=check_edge(cp,out/'runs/actual/edge-1',store.chain()[0],ROOT)
    assert checked['verdict']=='CHECKER_PASS'
    d=VerifiedChainDriver(ROOT,store,out/'recovery-runs',LEDGER)
    d._make_session=lambda *a:(_ for _ in ()).throw(AssertionError('recovery tried arbitrary resume'))
    stopped=d.run(3,'no-arbitrary-resume');assert stopped.verdict=='STOP' and stopped.state_id==sid
    assert markers(live)==[1] and not (live/'body-start-2.json').exists()
    save(out/'recovery.json',{'CURRENT':sid,'generation':state.generation,'receipt_hash_revalidated':True,'checkpoint_revalidated':True,'independent_edge_recheck':checked,'no_arbitrary_resume_result':asdict(stopped)})
    return {'verdict':'PASS','evidence_role':'LIVE','CURRENT':sid,'generation':1,'markers':[1],'controller_exit':75,'durable_generation_preserved':True,'formal_certification':False}

def main():
    if sys.argv[1]=='child':child(Path(sys.argv[2]),sys.argv[3]);return
    p=argparse.ArgumentParser();p.add_argument('stage');p.add_argument('run_id');p.add_argument('--positive-ref',default='positive-01');p.add_argument('--negative-ref',default='negative-01');a=p.parse_args()
    BASE.mkdir(parents=True,exist_ok=True);out=BASE/a.run_id;out.mkdir(exist_ok=False)
    pins=live_source_snapshot(ROOT);save(out/'source-pinset.json',pins)
    save(out/'pre-run.json',{'source_binding':content_id(pins),'root':str(ROOT),'run_id':a.run_id,'stage':a.stage,'ledger':str(LEDGER),'Gala_wheel_sha256':digest_bytes((ROOT/'audit/gate2c1/vendor/gala-1.12.0-cp312-cp312-manylinux_2_24_x86_64.manylinux_2_28_x86_64.whl').read_bytes()),'started_monotonic_ns':time.monotonic_ns(),'role':'actual Gala Task8; no TEST_ONLY fixture promotion'})
    started=time.perf_counter()
    try:
        if a.stage=='ordinary':result=run_control(out)
        elif a.stage in ('positive','negative'):result=run_live(out,3 if a.stage=='positive' else 4,a.stage=='negative')
        elif a.stage in ('nonterminal','terminal'):result=run_replay(out,a.stage=='terminal',a.positive_ref,a.negative_ref)
        elif a.stage in ('paused-death','active-death'):result=run_death(out,a.stage=='active-death')
        elif a.stage=='interruption':result=run_interruption(out)
        else:raise ValueError('unapproved Task8 stage')
        result.update(run_id=a.run_id,stage=a.stage,source_binding=content_id(pins),experiment_wall_seconds=time.perf_counter()-started)
        save(out/'SUMMARY.json',result);print(json.dumps(result))
    except BaseException as exc:
        save(out/'FAILED.json',{'type':type(exc).__name__,'reason':str(exc),'stage':a.stage,'run_id':a.run_id,'wall_seconds':time.perf_counter()-started,'source_binding':content_id(pins)})
        raise

if __name__=='__main__':main()

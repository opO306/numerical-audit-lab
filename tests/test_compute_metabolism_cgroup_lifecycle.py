"""Deterministic membership evidence cases; no LIVE or numerical authority."""
import os,copy
from pathlib import Path
import pytest
from compute_metabolism.v0 import system_guard as g
def setup_case(monkeypatch,tmp_path,*,states=('R','R','Z'),members=(True,False),groups=(True,True,True),exited=True,starts=('42','42','42'),missing=None,pid=123):
 path=tmp_path/'unit';path.mkdir();w=type('Witness',(),{})();w.start_ticks='42';w.pid=pid;w.closed=False;w.reads=0;w.cgreads=0
 def identity():
  i=w.reads;w.reads+=1
  if missing==i:raise FileNotFoundError('unproven disappeared')
  return dict(pid=pid,start_ticks=starts[min(i,len(starts)-1)],state=states[min(i,len(states)-1)])
 def cgroup():
  i=w.cgreads;w.cgreads+=1
  allowed=groups[min(i,len(groups)-1)]
  return '0::'+(str(path.relative_to(tmp_path)) if False else '/'+path.relative_to(tmp_path).as_posix() if allowed else '/outside')+'\n'
 w.identity=identity;w.cgroup=cgroup;w.exit_events=lambda: [(9,1)] if exited else [];w.close=lambda:setattr(w,'closed',True)
 def factory(p,owned):
  if missing=='bind':raise ProcessLookupError('unbound pidfd')
  return w
 monkeypatch.setattr(g,'CGROUP_ROOT',tmp_path)
 monkeypatch.setattr(g,'_ProcessWitness',factory,raising=False)
 monkeypatch.setattr(g,'_process_identity',lambda p:identity())
 calls=[]
 def membership(p):
  i=len(calls);calls.append(i);yes=members[min(i,len(members)-1)]
  return dict(pids=[pid] if yes else [],files=[dict(path=str(path/'cgroup.procs'),raw=str(pid)+'\n' if yes else '',begin_ns=i*2,end_ns=i*2+1)],begin_ns=i*2,end_ns=i*2+1,epoch=dict(path=str(path),device=1,inode=1,boot_id='fixture'))
 monkeypatch.setattr(g,'_cgroup_membership',membership,raising=False)
 monkeypatch.setattr(g,'_cgroup_pids',lambda p:membership(p)['pids'])
 return path,w,pid
def test_R_then_proven_terminal_owned_exit_is_accepted(monkeypatch,tmp_path):
 path,w,pid=setup_case(monkeypatch,tmp_path)
 ids,obs,current=g._sample_processes(path,[pid])
 assert obs[str(pid)]['status']=='exited_during_sample'
 assert obs[str(pid)]['exit_evidence']['basis']=='BOUND_PROCESS_PIDFD_AND_TERMINAL_OWNED_CGROUP'
 assert str(pid) not in ids and current==[] and w.closed
@pytest.mark.parametrize('attack',['alive','outside_first','outside_second','outside_terminal','reuse','gone_first','gone_terminal','unbound','wrapper'])
def test_unproven_exit_migration_and_reuse_refuse(monkeypatch,tmp_path,attack):
 kw={}
 if attack=='alive':kw['exited']=False
 if attack=='outside_first':kw['groups']=(False,)
 if attack=='outside_second':kw['groups']=(True,False)
 if attack=='outside_terminal':kw['groups']=(True,True,False)
 if attack=='reuse':kw['starts']=('42','43')
 if attack=='gone_first':kw['missing']=0
 if attack=='gone_terminal':kw['missing']=2
 if attack=='unbound':kw['missing']='bind'
 if attack=='wrapper':kw['pid']=os.getpid()
 path,w,pid=setup_case(monkeypatch,tmp_path,**kw)
 with pytest.raises(ValueError):g._sample_processes(path,[pid])
 if attack!='unbound':assert w.closed
def test_unproven_disappearance_never_becomes_exit(monkeypatch,tmp_path):
 path,w,pid=setup_case(monkeypatch,tmp_path,missing=0,members=(False,))
 with pytest.raises(ValueError):g._sample_processes(path,[pid])
def test_stable_membership_preserved(monkeypatch,tmp_path):
 path,w,pid=setup_case(monkeypatch,tmp_path,states=('R','R'),members=(True,),exited=False)
 ids,obs,current=g._sample_processes(path,[pid])
 assert ids[str(pid)]['start_ticks']=='42' and obs[str(pid)]['status']=='stable' and current==[pid] and w.closed
def test_terminal_membership_is_read_after_process_exit_event(monkeypatch,tmp_path):
 path,w,pid=setup_case(monkeypatch,tmp_path);order=[]
 old=w.cgroup;w.cgroup=lambda:(order.append('cgroup') or old())
 w.exit_events=lambda:(order.append('exit') or [(9,1)])
 g._sample_processes(path,[pid]);assert order[-2:]==['exit','cgroup']

@pytest.mark.parametrize('events',[[(9,8)],[(9,4)],[(10,1)],[(9,25)],[(9,1),(10,1)]])
def test_pidfd_bad_event_authority_refuses(monkeypatch,events):
 w=object.__new__(g._ProcessWitness);w.pidfd=9
 class Poll:
  def register(self,fd,mask):assert fd==9 and mask==g.select.POLLIN
  def poll(self,timeout):assert timeout==0;return events
 monkeypatch.setattr(g.select,'poll',Poll)
 with pytest.raises(ValueError):w.exit_events()
@pytest.mark.parametrize('failure',['none','pidfd_missing','birth_changed','numeric_reuse'])
def test_pinned_proc_and_pidfd_binding_and_all_fd_cleanup(monkeypatch,tmp_path,failure):
 closed=[];calls=[]
 monkeypatch.setattr(g.os,'open',lambda *a,**kw:21)
 def acquire(pid,flags):
  calls.append((pid,flags))
  if failure=='pidfd_missing':raise ProcessLookupError('ESRCH')
  return 22
 monkeypatch.setattr(g.os,'pidfd_open',acquire)
 monkeypatch.setattr(g.os,'close',closed.append)
 ticks=iter(['42','43' if failure=='birth_changed' else '42'])
 monkeypatch.setattr(g._ProcessWitness,'identity',lambda w:dict(pid=w.pid,start_ticks=next(ticks),state='R'))
 monkeypatch.setattr(g,'_process_identity',lambda pid:dict(pid=pid,start_ticks='43' if failure=='numeric_reuse' else '42',state='R'))
 if failure=='none':
  w=g._ProcessWitness(123,tmp_path);w.close();assert closed==[22,21]
 else:
  with pytest.raises((ProcessLookupError,ValueError)):g._ProcessWitness(123,tmp_path)
  assert closed==([21] if failure=='pidfd_missing' else [22,21])
 assert calls==[(123,0)]
def test_membership_file_inode_replacement_refuses(monkeypatch,tmp_path):
 monkeypatch.setattr(g,'_boot_id',lambda:'fixture')
 file=tmp_path/'cgroup.procs';file.write_text('123\n')
 original=Path.read_text
 def read(path,*args,**kwargs):
  raw=original(path,*args,**kwargs)
  if path==file:
   other=tmp_path/'swap';other.write_text(raw);other.replace(file)
  return raw
 monkeypatch.setattr(Path,'read_text',read)
 with pytest.raises(ValueError,match='identity'):g._cgroup_membership(tmp_path)
def test_missing_membership_file_refuses(tmp_path):
 with pytest.raises(FileNotFoundError):g._cgroup_membership(tmp_path)
def test_group_inventory_change_refuses(monkeypatch,tmp_path):
 monkeypatch.setattr(g,'_boot_id',lambda:'fixture')
 file=tmp_path/'cgroup.procs';file.write_text('123\n');original=Path.read_text
 def read(path,*args,**kwargs):
  raw=original(path,*args,**kwargs)
  if path==file:
   sub=tmp_path/'child';sub.mkdir();(sub/'cgroup.procs').write_text('456\n')
  return raw
 monkeypatch.setattr(Path,'read_text',read)
 with pytest.raises(ValueError,match='inventory'):g._cgroup_membership(tmp_path)
def test_group_epoch_change_refuses(monkeypatch,tmp_path):
 (tmp_path/'cgroup.procs').write_text('123\n')
 epochs=iter([dict(inode=1),dict(inode=2)])
 monkeypatch.setattr(g,'_epoch',lambda p:next(epochs))
 with pytest.raises(ValueError,match='epoch'):g._cgroup_membership(tmp_path)


def test_pinned_read_preserves_UTF8_comm_and_closes_fds(tmp_path):
    raw = '123 (작업) R 1 ' + '0 '*17 + '42 0\n'
    (tmp_path/'stat').write_text(raw,encoding='utf-8')
    witness=object.__new__(g._ProcessWitness)
    witness.pid=123;witness.pidfd=None;witness.procfd=os.open(tmp_path,os.O_RDONLY|os.O_DIRECTORY);witness.samples=[]
    fd=witness.procfd
    try:
        assert witness._read('stat')==raw
        assert witness.identity()['start_ticks']=='42'
    finally:witness.close()
    with pytest.raises(OSError):os.fstat(fd)


def test_exited_PID_reappears_in_final_list_refuses(monkeypatch,tmp_path):
    path,w,pid=setup_case(monkeypatch,tmp_path,members=(True,False,True))
    with pytest.raises(ValueError,match='reappeared'):g._sample_processes(path,[pid])
    assert w.closed


def test_leader_Z_without_whole_process_exit_refuses(monkeypatch,tmp_path):
    path,w,pid=setup_case(monkeypatch,tmp_path,states=('Z','Z','Z'),exited=False)
    with pytest.raises(ValueError):g._sample_processes(path,[pid])


def test_exit_event_with_terminal_R_refuses(monkeypatch,tmp_path):
    path,w,pid=setup_case(monkeypatch,tmp_path,states=('R','R','R'))
    with pytest.raises(ValueError):g._sample_processes(path,[pid])


def test_close_attempts_both_FDs_even_if_first_close_fails(monkeypatch):
    w=object.__new__(g._ProcessWitness);w.pidfd=22;w.procfd=21;closed=[]
    def close(fd):
        closed.append(fd)
        if fd==22:raise OSError('close failed')
    monkeypatch.setattr(g.os,'close',close)
    with pytest.raises(OSError):w.close()
    assert closed==[22,21] and w.pidfd is None and w.procfd is None

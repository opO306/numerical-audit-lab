from pathlib import Path
import copy, unittest
from compute_metabolism.v0 import cgroup_noescape as a_impl

def fixture():
 p={'trusted_kernel':True,'trusted_privileged_manager':True}
 r={'schema':'task9-ab-security-v1','expected_supplementary_groups':[1003],'unit':'test.service','boot_id':'boot','control_group':'/system.slice/test.service','host_user_namespace':'user:[1]','expected_cgroup_namespace':'cgroup:[2]','systemd':{'ControlGroup':'/system.slice/test.service','User':'1000','Group':'1003','Delegate':'no','NoNewPrivileges':'yes','CapabilityBoundingSet':'','AmbientCapabilities':'','ProtectControlGroups':'yes','RestrictNamespaces':'yes','RestrictSUIDSGID':'yes'},'trust':{'kernel_correct':True,'privileged_manager_no_migration_reconfiguration_or_proxy':True}}
 s={'status':{'Uid':'1000 1000 1000 1000','Gid':'1003 1003 1003 1003','Groups':'1003','CapEff':'0','CapPrm':'0','CapInh':'0','CapAmb':'0','CapBnd':'0','NoNewPrivs':'1','Seccomp':'2'},'namespaces':{'user':'user:[1]','cgroup':'cgroup:[2]'},'boot_id':'boot','cgroup':'0::/system.slice/test.service\n','mounts':[{'root':'/','point':'/sys/fs/cgroup','options':['ro'],'fstype':'cgroup2'}],'permissions':[{'path':'/sys/fs/cgroup','uid':0,'gid':0,'mode':0o755,'acl':[],'writable':False}],'control_fds':[],'epoch':{'path':'/sys/fs/cgroup/system.slice/test.service','device':1,'inode':2,'boot_id':'boot'}}
 s['permissions']=[dict(s['permissions'][0],path=d+n) for d in ['/sys/fs/cgroup','/sys/fs/cgroup/system.slice','/sys/fs/cgroup/system.slice/test.service'] for n in ['', '/cgroup.procs','/cgroup.threads','/cgroup.subtree_control']]
 s.update(uid_map='0 0 4294967295',gid_map='0 0 4294967295')
 return s,r,p
class ProofTests(unittest.TestCase):
 def test_valid(self):
  a_impl.validate_security(*fixture())
 def test_missing_trust(self):
  s,r,p=fixture(); p['trusted_kernel']=False
  with self.assertRaises(ValueError):a_impl.validate_security(s,r,p)
 def test_all_bad_security_fields(self):
  for key,bad in [('Uid','0 0 0 0'),('Gid','0 0 0 0'),('Groups','0 1003'),('CapEff','1'),('CapPrm','1'),('CapInh','1'),('CapAmb','1'),('CapBnd','1'),('NoNewPrivs','0'),('Seccomp','0')]:
   with self.subTest(key=key):
    s,r,p=fixture();s['status'][key]=bad
    with self.assertRaises(ValueError):a_impl.validate_security(s,r,p)
 def test_no_delegation_namespace_or_property_weakening(self):
  for key in fixture()[1]['systemd']:
   with self.subTest(key=key):
    s,r,p=fixture();r['systemd'][key]='bad'
    with self.assertRaises(ValueError):a_impl.validate_security(s,r,p)
 def test_mount_escape(self):
  for field,value in [('root','/system.slice'),('point','/other'),('options',['rw'])]:
   s,r,p=fixture();s['mounts'][0][field]=value
   with self.assertRaises(ValueError):a_impl.validate_security(s,r,p)
 def test_permissions(self):
  for field,value in [('uid',1000),('mode',0o777),('acl',['system.posix_acl_access']),('writable',True)]:
   s,r,p=fixture();s['permissions'][0][field]=value
   with self.assertRaises(ValueError):a_impl.validate_security(s,r,p)
 def test_identity_and_namespace(self):
  for field,value in [('boot_id','other'),('cgroup','0::/wrong'),('control_fds',['/sys/fs/cgroup/cgroup.procs'])]:
   s,r,p=fixture();s[field]=value
   with self.assertRaises(ValueError):a_impl.validate_security(s,r,p)
  for key in ['user','cgroup']:
   s,r,p=fixture();s['namespaces'][key]='other'
   with self.assertRaises(ValueError):a_impl.validate_security(s,r,p)
 def test_empty_proof(self):
  s,r,p=fixture();s['permissions']=[]
  with self.assertRaises(ValueError):a_impl.validate_security(s,r,p)


import types
from unittest.mock import patch
from compute_metabolism.v0 import cgroup_noescape_check as a_check
import hashlib,json
class SamplingTests(unittest.TestCase):
 def monitor(self,behavior):
  class Witness:
   def __init__(self,pid,path):
    self.pid=pid;self.start_ticks='99';self.samples=[]
    if pid==43 and behavior=='vanish':raise FileNotFoundError()
   def identity(self):return {'pid':self.pid,'start_ticks':'100' if self.pid==43 and behavior=='reuse' else '99','state':'R'}
   def close(self):pass
  def owned(w,p):
   if w.pid==43 and behavior=='escape':raise ValueError('live process outside owned cgroup')
   return '0::/system.slice/test.service'
  m=object.__new__(a_impl.Monitor)
  m.g=types.SimpleNamespace(_ProcessWitness=Witness,_owned_process_cgroup=owned,_cgroup_pids=lambda p:[42]);m.events=[];m.failed=None;m.security=lambda p:0;m.protected_pids={42};m.g._sample_processes=lambda *args:({},{},[])
  return m
 def test_disappearance_is_unknown_not_exit(self):
  m=self.monitor('vanish')
  with patch.object(a_impl.os,'getpid',return_value=42):ids,obs,pids=m.sample(Path('/test'),[42,43])
  self.assertNotIn('43',ids);self.assertIsNone(obs['43']['identity']);self.assertFalse(obs['43']['individual_exit_proven']);self.assertEqual(m.events[1]['status'],'IDENTITY_UNKNOWN')
 def test_live_escape_refused(self):
  with patch.object(a_impl.os,'getpid',return_value=42):
   with self.assertRaisesRegex(ValueError,'outside'):self.monitor('escape').sample(Path('/test'),[42,43])
 def test_pid_reuse_refused(self):
  with patch.object(a_impl.os,'getpid',return_value=42):
   with self.assertRaisesRegex(ValueError,'reuse'):self.monitor('reuse').sample(Path('/test'),[42,43])
 def test_wrapper_missing_refused(self):
  with patch.object(a_impl.os,'getpid',return_value=42):
   with self.assertRaisesRegex(ValueError,'wrapper'):self.monitor('ok').sample(Path('/test'),[43])
class CheckerTests(unittest.TestCase):
 def proof(self):
  s,r,p=fixture();r['systemd'].update(AllowedCPUs='0-1',EffectiveCPUs='0-1',MemoryMax='4294967296',MemorySwapMax='0');raw=json.dumps(r);p.update(security_record_path='/test',security_record_sha256=hashlib.sha256(raw.encode()).hexdigest())
  proof=dict(wrapper_pid=42,schema='task9-a-proof-v1',status='CONDITIONAL_GROUP_PROOF',error=None,policy=p,security_record=r,security_record_raw=raw,snapshots=[dict(monotonic_ns=i,evidence=copy.deepcopy(s)) for i in range(3)],events=[])
  stat='42 (wrapper) R 1 '+' '.join(['0']*17)+' 99'
  identity=dict(pid=42,start_ticks='99',state='R')
  proof['events']=[dict(pid=42,security_index=0,status='BOUND_IDENTITY',first=identity,second=identity,cgroups=['0::/system.slice/test.service']*2,process_samples=[dict(kind='stat',raw=stat,identity=copy.deepcopy(identity),ppid=1) for _ in range(3)]+[dict(kind='cgroup',raw='0::/system.slice/test.service'),dict(kind='stat',raw=stat,identity=copy.deepcopy(identity),ppid=1),dict(kind='cgroup',raw='0::/system.slice/test.service')])]
  return proof,p
 def test_scope_without_outer_not_pass(self):
  q,p=self.proof();self.assertEqual(a_check.check_proof(q,p)['status'],'CONDITIONAL_GROUP_PROOF')
 def test_hash_tamper(self):
  q,p=self.proof();q['security_record_raw']+=' ';self.assertEqual(a_check.check_proof(q,p)['status'],'REFUSED')
 def test_missing_evidence(self):
  q,p=self.proof();q['snapshots']=[];self.assertEqual(a_check.check_proof(q,p)['status'],'REFUSED')
 def test_fabricated_exit(self):
  q,p=self.proof();q['events']=[dict(pid=44,security_index=0,status='IDENTITY_UNKNOWN',identity=None,individual_exit_proven=True)];self.assertEqual(a_check.check_proof(q,p)['status'],'REFUSED')
 def test_epoch_change(self):
  q,p=self.proof();q['snapshots'][-1]['evidence']['epoch']['inode']=99;self.assertEqual(a_check.check_proof(q,p)['status'],'REFUSED')
 def test_incomplete_permission_inventory(self):
  q,p=self.proof()
  for x in q['snapshots']:x['evidence']['permissions'].pop()
  self.assertEqual(a_check.check_proof(q,p)['status'],'REFUSED')
 def test_external_move_and_return_without_trust_refused(self):
  q,p=self.proof();p['trusted_privileged_manager']=False;self.assertEqual(a_check.check_proof(q,p)['status'],'REFUSED')


class OuterClosureTests(unittest.TestCase):
 proof=CheckerTests.proof
 def full(self):
  q,p=self.proof();r=q['security_record'];r['systemd'].update(Id='test.service',ExecMainPID='42');q['security_record_raw']=json.dumps(r);p['security_record_sha256']=hashlib.sha256(q['security_record_raw'].encode()).hexdigest()
  before=dict(epoch=q['snapshots'][0]['evidence']['epoch'],monotonic_seconds=1.0,cpu_stat={'usage_usec':10,'user_usec':8,'system_usec':2},memory_peak=100,memory_events={'oom':0,'oom_kill':0},cpus=[0,1],memory={'effective_bytes':4294967296},swap={'effective_bytes':0},raw={'memory.max':'4294967296','memory.swap.max':'0'},pids=[42],process_identities={'42':{'pid':42,'start_ticks':'99','state':'R'}})
  after=copy.deepcopy(before);after.update(monotonic_seconds=2.0,cpu_stat={'usage_usec':20,'user_usec':16,'system_usec':4})
  for snap in (before,after): complete_raw_fixture(snap)
  delta={'usage_usec':10,'user_usec':8,'system_usec':2,'cpu_seconds':0.00001}
  g=dict(run_id='run-test',unit='test.service',profile='2c',measurement_valid=True,outcome='GUARD_COMPLETE',child_returncode=0,containment={'remaining_pids':[]},wrapper_identity={'pid':42,'start_ticks':'99'},before=before,after=after,delta=delta)
  end=dict(raw=''.join(k+'='+v+'\n' for k,v in r['systemd'].items()),props=copy.deepcopy(r['systemd']),monotonic_ns=2000000001)
  o=dict(run_id=g['run_id'],unit=g['unit'],profile=g['profile'],terminal=True,launcher_reaped=True,security_end_unchanged=True,outcome='GUARD_COMPLETE',measurement_valid=True,before=copy.deepcopy(before),after=copy.deepcopy(after),delta=copy.deepcopy(delta),security_end_record=end,cleanup_attempts=[],outer_timeout_proved=False,returncode=0)
  return q,p,g,o
 def test_full_valid(self):
  self.assertEqual(a_check.check_proof(*self.full())['status'],'PASS')
 def test_outer_failed_outcome(self):
  for outcome in ['ENVIRONMENT_INVALID','REFUSED_RESOURCE','UNRESOLVED_FAILURE']:
   q,p,g,o=self.full();o['outcome']=outcome
   with self.subTest(outcome=outcome):self.assertEqual(a_check.check_proof(q,p,g,o)['status'],'REFUSED')
 def test_outer_invalid_measurement(self):
  q,p,g,o=self.full();o['measurement_valid']=False;self.assertEqual(a_check.check_proof(q,p,g,o)['status'],'REFUSED')
 def test_outer_error_and_timeout(self):
  for field,value in [('outer_timeout_proved',True),('error','error'),('errors',['error']),('cleanup_errors',['error']),('terminal_errors',['error']),('cleanup_attempts',[{'errors':['stop failed']}])]:
   q,p,g,o=self.full();o[field]=value
   with self.subTest(field=field):self.assertEqual(a_check.check_proof(q,p,g,o)['status'],'REFUSED')
 def test_outer_identity_mismatch(self):
  for field in ['run_id','unit','profile']:
   q,p,g,o=self.full();o[field]='wrong'
   with self.subTest(field=field):self.assertEqual(a_check.check_proof(q,p,g,o)['status'],'REFUSED')
 def test_outer_snapshot_or_delta_mismatch(self):
  for field in ['before','after','delta']:
   q,p,g,o=self.full();o[field]={}
   with self.subTest(field=field):self.assertEqual(a_check.check_proof(q,p,g,o)['status'],'REFUSED')
 def test_delta_forged_consistently(self):
  q,p,g,o=self.full();g['delta']['cpu_seconds']=9;o['delta']=copy.deepcopy(g['delta']);self.assertEqual(a_check.check_proof(q,p,g,o)['status'],'REFUSED')
 def test_end_record_missing(self):
  q,p,g,o=self.full();del o['security_end_record'];self.assertEqual(a_check.check_proof(q,p,g,o)['status'],'REFUSED')
 def test_end_record_inconsistent(self):
  for field,value in [('raw','Delegate=yes\n'),('props',{}),('monotonic_ns',1000000000)]:
   q,p,g,o=self.full();o['security_end_record'][field]=value
   with self.subTest(field=field):self.assertEqual(a_check.check_proof(q,p,g,o)['status'],'REFUSED')
 def test_end_record_wrong_process(self):
  q,p,g,o=self.full();o['security_end_record']['props']['ExecMainPID']='99';self.assertEqual(a_check.check_proof(q,p,g,o)['status'],'REFUSED')


class SupplementaryGroupTests(unittest.TestCase):
 def test_frozen_additional_groups_allowed(self):
  s,r,p=fixture();s['status']['Groups']='4 24 27 1000 1003';r['expected_supplementary_groups']=[4,24,27,1000,1003];a_impl.validate_security(s,r,p)
 def test_missing_expected_groups(self):
  s,r,p=fixture();del r['expected_supplementary_groups']
  with self.assertRaises(ValueError):a_impl.validate_security(s,r,p)
 def test_malformed_frozen_groups(self):
  for bad in [None,'1003',[True],[1003,1003],[1003,4],[-1],[0],[4294967295]]:
   s,r,p=fixture();r['expected_supplementary_groups']=bad
   with self.subTest(bad=bad):
    with self.assertRaises(ValueError):a_impl.validate_security(s,r,p)
 def test_malformed_actual_groups(self):
  for bad in ['+1003','01003','1003 1003','1003 4','-1','0','1003 extra']:
   s,r,p=fixture();s['status']['Groups']=bad
   with self.subTest(bad=bad):
    with self.assertRaises(ValueError):a_impl.validate_security(s,r,p)
 def test_groups_in_invariant(self):
  s,r,p=fixture();after=copy.deepcopy(s);after['status']['Groups']='4 1003';self.assertNotEqual(a_impl.invariant(s),a_impl.invariant(after))
 def test_additional_group_cannot_authorize_write(self):
  for field,bad in [('mode',0o775),('writable',True),('acl',['system.posix_acl_access'])]:
   s,r,p=fixture();s['status']['Groups']='4 1003';r['expected_supplementary_groups']=[4,1003];s['permissions'][0].update(gid=4);s['permissions'][0][field]=bad
   with self.subTest(field=field):
    with self.assertRaises(ValueError):a_impl.validate_security(s,r,p)
 def rebound(self,groups):
  q,p=CheckerTests().proof();q['security_record']['expected_supplementary_groups']=groups;q['security_record_raw']=json.dumps(q['security_record']);p['security_record_sha256']=hashlib.sha256(q['security_record_raw'].encode()).hexdigest();return q,p
 def test_checker_additional_frozen_groups(self):
  q,p=self.rebound([4,1003])
  for row in q['snapshots']:row['evidence']['status']['Groups']='4 1003'
  self.assertEqual(a_check.check_proof(q,p)['status'],'CONDITIONAL_GROUP_PROOF')
 def test_checker_group_drift(self):
  q,p=self.rebound([4,1003])
  for row in q['snapshots']:row['evidence']['status']['Groups']='4 1003'
  q['snapshots'][-1]['evidence']['status']['Groups']='1003';self.assertEqual(a_check.check_proof(q,p)['status'],'REFUSED')
 def test_checker_missing_frozen_groups(self):
  q,p=CheckerTests().proof();del q['security_record']['expected_supplementary_groups'];q['security_record_raw']=json.dumps(q['security_record']);p['security_record_sha256']=hashlib.sha256(q['security_record_raw'].encode()).hexdigest();self.assertEqual(a_check.check_proof(q,p)['status'],'REFUSED')



def complete_raw_fixture(s):
 leaf=s['epoch']['path'];roots=[leaf,'/sys/fs/cgroup/system.slice','/sys/fs/cgroup']
 s['cpu_stat']['nice_usec']=0;s['memory_current']=80;s['enumerated_pids']=list(s['pids'])
 for field,name,value in [('memory','memory.max',4294967296),('swap','memory.swap.max',0)]:
  s[field]={'effective_bytes':value,'scan_root':'/sys/fs/cgroup','ancestors':[{'path':roots[0]+'/'+name,'raw':str(value)+'\n','bytes':value},{'path':roots[1]+'/'+name,'raw':'max\n','bytes':None},{'path':roots[2]+'/'+name,'raw':None,'missing_at_root':True}]}
 ancestors=[{'path':roots[0]+'/cpu.max','raw':None,'missing_at_root':False},{'path':roots[1]+'/cpu.max','raw':'max 100000\n','quota_usec':None,'period_usec':100000},{'path':roots[2]+'/cpu.max','raw':None,'missing_at_root':True}]
 s['cpu_max']={'ancestors':ancestors,'finite_ancestors':[],'source':roots[1]+'/cpu.max','raw':'max 100000\n','quota_usec':None,'period_usec':100000,'unlimited':True,'scan_root':'/sys/fs/cgroup'}
 s['raw'].update({'memory.max':'4294967296\n','memory.swap.max':'0\n','cpu.stat':''.join(k+' '+str(v)+'\n' for k,v in s['cpu_stat'].items()),'cpuset.cpus.effective':'0-1\n','memory.current':'80\n','memory.peak':str(s['memory_peak'])+'\n','memory.events':''.join(k+' '+str(v)+'\n' for k,v in s['memory_events'].items()),'cgroup.procs':''.join(str(v)+'\n' for v in s['pids']),'cgroup.events':'populated 1\nfrozen 0\n','cpu.max':'max 100000\n'})

class RawBindingTests(unittest.TestCase):
 full=OuterClosureTests.full
 proof=CheckerTests.proof
 def refused(self,q,p,g,o):
  o['before']=copy.deepcopy(g['before']);o['after']=copy.deepcopy(g['after']);o['delta']=copy.deepcopy(g['delta'])
  self.assertEqual(a_check.check_proof(q,p,g,o)['status'],'REFUSED')
 def test_raw_only_tamper(self):
  for name,value in [('cpu.stat','usage_usec 21\nuser_usec 16\nsystem_usec 4\nnice_usec 0\n'),('memory.peak','101\n'),('memory.current','81\n'),('memory.events','oom 0\noom_kill 1\n'),('cpuset.cpus.effective','0\n'),('cgroup.procs','43\n'),('cgroup.events','populated 0\nfrozen 0\n'),('cpu.max','1000 100000\n')]:
   q,p,g,o=self.full();g['after']['raw'][name]=value
   with self.subTest(field=name):self.refused(q,p,g,o)
 def test_forged_cpu_and_delta_with_unchanged_raw(self):
  q,p,g,o=self.full();g['after']['cpu_stat']['usage_usec']+=1000000;g['delta']['usage_usec']+=1000000;g['delta']['cpu_seconds']=g['delta']['usage_usec']/1000000;self.refused(q,p,g,o)
 def test_nice_counter_bound_even_not_in_delta(self):
  q,p,g,o=self.full();g['after']['cpu_stat']['nice_usec']=1;self.refused(q,p,g,o)
 def test_bad_numeric_rows(self):
  for raw in ['usage_usec 20\nusage_usec 20\nuser_usec 16\nsystem_usec 4\n','usage_usec -1\nuser_usec 16\nsystem_usec 4\n','usage_usec +20\nuser_usec 16\nsystem_usec 4\n','usage_usec ２０\nuser_usec 16\nsystem_usec 4\n','usage_usec 18446744073709551616\nuser_usec 16\nsystem_usec 4\n','usage_usec 20 1\nuser_usec 16\nsystem_usec 4\n','usage_usec 20\n\nuser_usec 16\nsystem_usec 4\n','usage_usec 20\nuser_usec 16\n']:
   q,p,g,o=self.full();g['after']['raw']['cpu.stat']=raw
   with self.subTest(raw=raw):self.refused(q,p,g,o)
 def test_missing_raw_fields(self):
  for name in ['cpu.stat','memory.peak','memory.current','memory.events','cpuset.cpus.effective','cgroup.procs','cgroup.events','cpu.max']:
   q,p,g,o=self.full();del g['after']['raw'][name]
   with self.subTest(field=name):self.refused(q,p,g,o)
 def test_boolean_and_float_parsed_counter_refused(self):
  for value in [True,20.0]:
   q,p,g,o=self.full();g['after']['cpu_stat']['usage_usec']=value
   with self.subTest(value=value):self.refused(q,p,g,o)
 def test_memory_ancestor_raw_mismatch(self):
  q,p,g,o=self.full();g['after']['memory']['ancestors'][1]['raw']='2147483648\n';self.refused(q,p,g,o)
 def test_cpu_ancestor_source_mismatch(self):
  for field,value in [('source','/wrong'),('quota_usec',1),('unlimited',False),('finite_ancestors',[{}])]:
   q,p,g,o=self.full();g['after']['cpu_max'][field]=value
   with self.subTest(field=field):self.refused(q,p,g,o)
 def test_ancestor_missing_or_reordered(self):
  for field in ['memory','swap','cpu_max']:
   q,p,g,o=self.full();g['after'][field]['ancestors'].reverse()
   with self.subTest(field=field):self.refused(q,p,g,o)
 def test_cgroup_events_optional_structured_mismatch(self):
  q,p,g,o=self.full();g['after']['cgroup_events']={'populated':0,'frozen':0};self.refused(q,p,g,o)
 def test_cpu_list_duplicate_rejected(self):
  q,p,g,o=self.full();g['after']['raw']['cpuset.cpus.effective']='0-1,1\n';self.refused(q,p,g,o)
 def test_finite_cpu_quota_not_2c_unlimited(self):
  q,p,g,o=self.full();c=g['after']['cpu_max'];e=c['ancestors'][1];e.update(raw='50000 100000\n',quota_usec=50000);c.update(raw=e['raw'],quota_usec=50000,unlimited=False,finite_ancestors=[copy.deepcopy(e)]);g['after']['raw']['cpu.max']=e['raw'];self.refused(q,p,g,o)
 def test_root_resource_record_mismatch(self):
  q,p,g,o=self.full();q['security_record']['systemd']['MemoryMax']='1';q['security_record_raw']=json.dumps(q['security_record']);p['security_record_sha256']=hashlib.sha256(q['security_record_raw'].encode()).hexdigest();o['security_end_record']['props']=copy.deepcopy(q['security_record']['systemd']);o['security_end_record']['raw']=''.join(k+'='+v+'\n' for k,v in o['security_end_record']['props'].items());self.refused(q,p,g,o)


class ProcessRawBindingTests(unittest.TestCase):
 proof=CheckerTests.proof
 def test_raw_process_cgroup_tamper(self):
  q,p=self.proof();q['events'][0]['process_samples'][3]['raw']='0::/outside\n';self.assertEqual(a_check.check_proof(q,p)['status'],'REFUSED')
 def test_embedded_raw_stat_identity_mismatch(self):
  for field,value in [('pid',43),('start_ticks','100'),('state','Z')]:
   q,p=self.proof();q['events'][0]['process_samples'][0]['identity'][field]=value
   with self.subTest(field=field):self.assertEqual(a_check.check_proof(q,p)['status'],'REFUSED')
 def test_embedded_parent_mismatch(self):
  q,p=self.proof();q['events'][0]['process_samples'][0]['ppid']=2;self.assertEqual(a_check.check_proof(q,p)['status'],'REFUSED')
 def test_event_state_mismatch(self):
  q,p=self.proof();q['events'][0]['second']=dict(q['events'][0]['second'],state='Z');self.assertEqual(a_check.check_proof(q,p)['status'],'REFUSED')
 def test_legitimate_state_transition(self):
  q,p=self.proof();event=q['events'][0];event['second']=dict(event['second'],state='Z');sample=event['process_samples'][4];sample['raw']=sample['raw'].replace(') R ',') Z ');sample['identity']['state']='Z';self.assertEqual(a_check.check_proof(q,p)['status'],'CONDITIONAL_GROUP_PROOF')
if __name__=='__main__':unittest.main(verbosity=2)

"""TEST_ONLY A: conditional noescape proof; unknown PID identities stay unknown."""
import errno, hashlib, json, os, stat, time
from pathlib import Path

def require(value, reason):
    if not value: raise ValueError('A REFUSED: '+reason)

def validate_security(s,r,p):
    require(p.get('trusted_kernel') is True and p.get('trusted_privileged_manager') is True,'trust policy missing')
    require(r.get('schema')=='task9-ab-security-v1','security record schema')
    require(r.get('trust',{}).get('kernel_correct') is True and r.get('trust',{}).get('privileged_manager_no_migration_reconfiguration_or_proxy') is True,'frozen trust missing')
    x=s['status']
    require(x['Uid'].split()==[str(r.get('execution_identity',{'uid':1000})['uid'])]*4 and x['Gid'].split()==[str(r.get('execution_identity',{'gid':1003})['gid'])]*4,'execution IDs')
    frozen_groups=r.get('expected_supplementary_groups')
    require(isinstance(frozen_groups,list) and all(type(v) is int and 0<v<4294967295 for v in frozen_groups),'missing or malformed frozen supplementary groups')
    require(frozen_groups==sorted(set(frozen_groups)),'frozen supplementary groups must be sorted unique')
    actual_groups=x['Groups'].split()
    require(all(v.isascii() and v.isdecimal() and str(int(v))==v and 0<int(v)<4294967295 for v in actual_groups),'malformed actual supplementary groups')
    actual_groups=list(map(int,actual_groups))
    require(actual_groups==sorted(set(actual_groups)) and actual_groups==frozen_groups,'supplementary groups differ from frozen actual credentials')
    require(all(int(x[k],16)==0 for k in ('CapEff','CapPrm','CapInh','CapAmb','CapBnd')),'capabilities')
    require(x['NoNewPrivs']=='1' and x['Seccomp']=='2','NNP or seccomp absent')
    require(s['boot_id']==r['boot_id'],'boot binding')
    require(s['namespaces']['user']==r['host_user_namespace'],'user namespace')
    require(s['namespaces']['cgroup']==r['expected_cgroup_namespace'],'cgroup namespace')
    require(s['cgroup'].strip()=='0::'+r['control_group'],'wrong actual cgroup')
    require(r['control_group']=='/system.slice/'+r['unit'],'unit controlgroup')
    props={'ControlGroup':r['control_group'],'User':str(r.get('execution_identity',{'uid':1000})['uid']),'Group':str(r.get('execution_identity',{'gid':1003})['gid']),'Delegate':'no','NoNewPrivileges':'yes','CapabilityBoundingSet':'','AmbientCapabilities':'','ProtectControlGroups':'yes','RestrictNamespaces':'yes','RestrictSUIDSGID':'yes'}
    require(all(str(r['systemd'].get(k))==v for k,v in props.items()),'effective systemd security properties')
    require(bool(s['mounts']),'cgroup mount missing')
    require(all(m['fstype']=='cgroup2' and m['root']=='/' and m['point']=='/sys/fs/cgroup' and 'ro' in m['options'] and 'rw' not in m['options'] for m in s['mounts']),'cgroup mount or alias')
    require(bool(s['permissions']),'permission evidence missing')
    required=set()
    for directory in ('/sys/fs/cgroup','/sys/fs/cgroup/system.slice','/sys/fs/cgroup'+r['control_group']):
        required.update((directory,directory+'/cgroup.procs',directory+'/cgroup.threads',directory+'/cgroup.subtree_control'))
    require(required <= {v['path'] for v in s['permissions']},'incomplete permission inventory')
    require(all(v['uid']==0 and not v['mode'] & 0o022 and not v['acl'] and not v['writable'] for v in s['permissions']),'ancestor permissions/ACL')
    require(not s['control_fds'],'inherited cgroup control descriptor')
    require(s['epoch']['path']=='/sys/fs/cgroup'+r['control_group'] and s['epoch']['boot_id']==r['boot_id'],'cgroup epoch binding')

def read_record(p):
    path=Path(p['security_record_path'])
    st=path.stat()
    require(st.st_uid==0 and not st.st_mode & 0o022,'security record permissions')
    raw=path.read_bytes()
    require(hashlib.sha256(raw).hexdigest()==p['security_record_sha256'],'security record digest')
    return json.loads(raw)

def collect(g,path):
    status={line.split(':',1)[0]:line.split(':',1)[1].strip() for line in Path('/proc/self/status').read_text().splitlines() if ':' in line}
    mounts=[]
    for line in Path('/proc/self/mountinfo').read_text().splitlines():
        left,right=line.split(' - ',1); f=left.split(); tail=right.split()
        if tail[0] in ('cgroup','cgroup2'):
            mounts.append(dict(root=f[3],point=f[4],options=f[5].split(','),fstype=tail[0]))
    permissions=[]
    for ancestor in g._ancestors(path):
        for file in [ancestor, *[ancestor/n for n in ('cgroup.procs','cgroup.threads','cgroup.subtree_control','cpu.max','memory.max','memory.swap.max') if (ancestor/n).exists()]]:
            st=file.stat()
            try:
                acl=[x for x in os.listxattr(file) if 'acl' in x]
                acl_status='LISTXATTR_OK'
            except OSError as exc:
                if exc.errno not in (errno.ENOTSUP,errno.EOPNOTSUPP):raise
                acl=[];acl_status='FILESYSTEM_NO_XATTR_SUPPORT'
            permissions.append(dict(path=str(file),uid=st.st_uid,gid=st.st_gid,mode=stat.S_IMODE(st.st_mode),device=st.st_dev,inode=st.st_ino,acl=acl,acl_status=acl_status,writable=os.access(file,os.W_OK,effective_ids=True)))
    fds=[]
    for fd in Path('/proc/self/fd').iterdir():
        try: target=os.readlink(fd)
        except FileNotFoundError:continue
        if target.startswith('/sys/fs/cgroup'):fds.append(target)
    return dict(status=status,namespaces={n:os.readlink('/proc/self/ns/'+n) for n in ('user','cgroup','mnt','pid')},uid_map=Path('/proc/self/uid_map').read_text(),gid_map=Path('/proc/self/gid_map').read_text(),boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),cgroup=Path('/proc/self/cgroup').read_text(),mounts=mounts,permissions=permissions,control_fds=fds,epoch=g._epoch(path))

def invariant(s):
    return dict(supplementary_groups=list(map(int,s['status']['Groups'].split())),**{k:s[k] for k in ('namespaces','uid_map','gid_map','boot_id','cgroup','mounts','permissions','epoch')})

class Monitor:
    def __init__(self,g,artifact_dir,policy):
        self.g,self.dir,self.policy=g,Path(artifact_dir),dict(policy)
        self.record=read_record(policy);self.record_raw=Path(policy['security_record_path']).read_text();self.snapshots=[];self.events=[];self.failed=None;self.initial=None;self.path=None;self.protected_pids={os.getpid()}
    def security(self,path):
        current=read_record(self.policy)
        require(current==self.record,'frozen record changed')
        s=collect(self.g,path)
        self.snapshots.append(dict(monotonic_ns=time.monotonic_ns(),evidence=s))
        validate_security(s,self.record,self.policy)
        if self.initial is None:self.initial=invariant(s)
        require(invariant(s)==self.initial,'security/ancestor epoch changed')
        return len(self.snapshots)-1
    def sample(self,path,enumerated):
        self.path=path
        try:
            proof_index=self.security(path);self.last_security_index=proof_index
            identities,observations={},{}
            for pid in enumerated:
                w=None;ev=dict(pid=pid,security_index=proof_index)
                try:
                    if pid in self.protected_pids:
                        strict_ids,strict_observations,strict_current=self.g._sample_processes(path,[pid])
                        ev['required_individual_evidence']=dict(identities=strict_ids,observations=strict_observations,current_pids=strict_current)
                    w=self.g._ProcessWitness(pid,path)
                    first=w.identity();cg1=self.g._owned_process_cgroup(w,path)
                    second=w.identity();cg2=self.g._owned_process_cgroup(w,path)
                    require(first['start_ticks']==second['start_ticks']==w.start_ticks,'PID reuse')
                    identities[str(pid)]=second
                    observations[str(pid)]=dict(status='group_accounted_bound_identity',identity=second,individual_exit_proven=False)
                    ev.update(status='BOUND_IDENTITY',first=first,second=second,cgroups=[cg1,cg2],process_samples=w.samples)
                except (FileNotFoundError,ProcessLookupError):
                    require(pid not in self.protected_pids,'required individual process identity vanished')
                    observations[str(pid)]=dict(status='group_accounted_identity_unknown',identity=None,individual_exit_proven=False,basis='FROZEN_CONDITIONAL_NOESCAPE')
                    ev.update(status='IDENTITY_UNKNOWN',identity=None,individual_exit_proven=False)
                finally:
                    if w is not None:w.close()
                    self.events.append(ev)
            current=self.g._cgroup_pids(path)
            for pid in current:
                if pid not in enumerated:
                    observations[str(pid)]=dict(status='appeared_during_sample',identity=None,individual_exit_proven=False)
            require(str(os.getpid()) in identities,'wrapper identity unavailable')
            self.last_security_end_index=self.security(path)
            return identities,observations,current
        except Exception as exc:
            self.failed=str(exc);raise
    def finish(self):
        try:
            require(self.path is not None and self.initial is not None,'no successful baseline proof')
            self.security(self.path)
        except Exception as exc:self.failed=str(exc)
        value=dict(schema='task9-a-proof-v1',wrapper_pid=os.getpid(),status='REFUSED' if self.failed else 'CONDITIONAL_GROUP_PROOF',error=self.failed,policy=self.policy,security_record=self.record,security_record_raw=self.record_raw,snapshots=self.snapshots,events=self.events,scope='GROUP_ACCOUNTING_ONLY; individual unseen birth, identity, and exit UNKNOWN; privileged manager noninterference is an assumption')
        self.g._write_json(self.dir/'a_security_proof.json',value)
        return value

def configure(g,artifact_dir,policy):
    m=Monitor(g,artifact_dir,policy)
    return m

"""Root manager evidence for one explicitly approved conditional A guard run."""
import hashlib, json, os, pwd, stat, subprocess, threading, time
from pathlib import Path

PROPERTIES=('Id','ControlGroup','User','Group','Delegate','NoNewPrivileges','CapabilityBoundingSet','AmbientCapabilities','ProtectControlGroups','RestrictNamespaces','RestrictSUIDSGID','AllowedCPUs','EffectiveCPUs','MemoryMax','MemorySwapMax','ExecMainPID','MainPID')
INNER_DIRECTORY='/run/cm-a'
TRUST_SCOPE='correct_kernel_and_approved_privileged_manager_noninterference_for_this_run'

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()+b'\n'
def digest(value): return hashlib.sha256(value).hexdigest()
def publish(path,value):
    raw=canonical(value); temporary=path.with_name('.'+path.name+'.publishing')
    with temporary.open('xb') as out: out.write(raw);out.flush();os.fsync(out.fileno())
    os.chmod(temporary,0o444);os.chown(temporary,0,0);os.rename(temporary,path)
    return digest(raw)
def immutable(path):
    st=path.lstat()
    if not stat.S_ISREG(st.st_mode) or st.st_uid!=0 or st.st_gid!=0 or stat.S_IMODE(st.st_mode)!=0o444 or st.st_nlink!=1:
        raise ValueError('A immutable root evidence ownership')
    return json.loads(path.read_bytes())
def validate_authority(profile,required,authority):
    if type(required) is not bool:raise ValueError('A requirement must be explicit boolean')
    if not required:return None
    if profile.key!='2c':raise ValueError('A supported only for 2c')
    if not isinstance(authority,dict):raise ValueError('A authority missing')
    trust=authority.get('trust_approval',{})
    if (authority.get('scope') not in ('TEST_ONLY','LIVE') or not isinstance(authority.get('authority_id'),str) or not authority['authority_id']
        or not isinstance(trust.get('approved_by'),str) or not trust['approved_by'] or trust.get('scope')!=authority['scope'] or trust.get('noninterference_scope')!=TRUST_SCOPE
        or trust.get('kernel_correct') is not True or trust.get('privileged_manager_no_migration_reconfiguration_or_proxy') is not True):
        raise ValueError('A authority explicit scoped trust approval missing')
    sources=authority.get('source_manifest')
    if not isinstance(sources,dict) or not sources:raise ValueError('A authority approved source manifest missing')
    for name,want in sources.items():
        if (not isinstance(name,str) or Path(name).is_absolute() or '..' in Path(name).parts or not isinstance(want,str)
            or len(want)!=64 or any(c not in '0123456789abcdef' for c in want)):
            raise ValueError('A authority source manifest malformed')
    required_sources={'compute_metabolism/v0/system_guard.py','compute_metabolism/v0/cgroup_noescape.py','compute_metabolism/v0/cgroup_noescape_policy.py','compute_metabolism/v0/cgroup_noescape_check.py'}
    if not required_sources<=sources.keys():raise ValueError('A authority guard/checker sources missing')
    return authority

def verify_sources(root,manifest):
    for name,want in manifest.items():
        p=(root/'workspace'/name);info=p.lstat()
        if not stat.S_ISREG(info.st_mode) or p.resolve()!=p or digest(p.read_bytes())!=want:
            raise ValueError('A approved source differs from actual root: '+name)

class Manager:
    def __init__(self, *, authority, root, artifact_dir, configuration, identity):
        if os.geteuid()!=0:raise ValueError('A root manager required')
        self.root=Path(root);self.artifact_dir=Path(artifact_dir);self.configuration=configuration
        verify_sources(self.root,authority['source_manifest'])
        if authority['scope']=='LIVE':
            from . import source_epoch, campaign
            epoch=authority.get('source_epoch')
            if not isinstance(epoch,dict):raise ValueError('A LIVE frozen source epoch missing')
            _,v1_binding=source_epoch.validate_epoch(epoch,self.root/'workspace')
            if authority.get('v1_source_binding')!=v1_binding:raise ValueError('A LIVE source epoch binding')
            campaign.validate_gate_source_snapshot(authority['source_manifest'],self.root/'workspace',epoch)
        self.dir=Path(authority['evidence_root']).resolve(strict=True)/configuration['run_id']
        parent=self.dir.parent;info=parent.stat()
        if info.st_uid!=0 or info.st_mode & 0o022:raise ValueError('A manager parent not root protected')
        self.dir.mkdir(mode=0o755);os.chown(self.dir,0,0)
        account=pwd.getpwuid(identity.uid)
        baseline=dict(uid=identity.uid,gid=identity.gid,nss_user=account.pw_name,nss_primary_gid=account.pw_gid,supplementary_groups=sorted(set(os.getgrouplist(account.pw_name,identity.gid))))
        self.credential_baseline=baseline
        self.binding=dict(credential_baseline=baseline,run_id=configuration['run_id'],unit=configuration['unit'],profile=configuration['profile'],configuration_sha256=digest(canonical(configuration)),source_manifest=dict(authority['source_manifest']),source_binding=digest(canonical(authority['source_manifest'])),authority_id=authority['authority_id'],scope=authority['scope'],trust_approval=dict(authority['trust_approval']))
        if authority['scope']=='LIVE': self.binding.update(source_epoch=authority['source_epoch'],v1_source_binding=authority['v1_source_binding'])
        self.manifest=dict(schema='cm-a-launch-v1',binding=self.binding,configuration=configuration,identity=dict(uid=identity.uid,gid=identity.gid))
        self.manifest_sha256=publish(self.dir/'launch-manifest.json',self.manifest)
        self.rows=[];self.preparation_rows=[];self.errors=[];self.policy=None;self.end=None;self.done=threading.Event();self.thread=None
    def read_actual(self):
        unit=self.configuration['unit']
        response=subprocess.run(['systemctl','show',unit,*[x for p in PROPERTIES for x in ('-p',p)]],capture_output=True,text=True,timeout=2)
        if response.returncode:raise ValueError('A systemctl show failed: '+response.stderr)
        props=dict(line.split('=',1) for line in response.stdout.splitlines())
        pid=int(props.get('ExecMainPID','0'))
        if not pid:return None
        if props['Id']!=unit or props['MainPID']!=str(pid):raise ValueError('A actual unit PID identity')
        proc=Path('/proc')/str(pid)
        return dict(monotonic_ns=time.monotonic_ns(),raw=response.stdout,properties=props,proc_status=(proc/'status').read_text(),proc_stat=(proc/'stat').read_text(),namespaces={n:os.readlink(proc/'ns'/n) for n in ('user','cgroup','mnt','pid')})
    def start(self):
        self.thread=threading.Thread(target=self.run,daemon=True);self.thread.start()
    def run(self):
        initial=None; deadline=time.monotonic()+min(10,self.configuration['deadline_seconds'])
        try:
            while not self.done.is_set():
                row=self.read_actual()
                if row is None:
                    if initial is not None:raise ValueError('A wrapper vanished before end handshake')
                    if time.monotonic()>deadline:raise ValueError('A initial actual unit timeout')
                    time.sleep(.01);continue
                if initial is None:
                    ready=self.artifact_dir/'a-wrapper-ready.json'
                    if not ready.exists():
                        self.preparation_rows.append(row);time.sleep(.01);continue
                    announced=json.loads(ready.read_bytes());pid=int(row['properties']['ExecMainPID']);birth=row['proc_stat'].rsplit(')',1)[1].split()[19]
                    if announced!=dict(unit=self.configuration['unit'],run_id=self.configuration['run_id'],pid=pid,start_ticks=birth):raise ValueError('A initial wrapper identity binding')
                    initial=row['properties']; status=dict(line.split(':',1) for line in row['proc_status'].splitlines() if ':' in line)
                    identity=self.manifest['identity']
                    if status['Uid'].split()!=[str(identity['uid'])]*4 or status['Gid'].split()!=[str(identity['gid'])]*4:raise ValueError('A actual proc execution credentials')
                    if sorted(set(map(int,status['Groups'].split())))!=self.credential_baseline['supplementary_groups']:raise ValueError('A actual supplemental groups differ from independent approved executor NSS')
                    record=dict(schema='task9-ab-security-v1',unit=self.configuration['unit'],boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),control_group=initial['ControlGroup'],host_user_namespace=os.readlink('/proc/1/ns/user'),expected_cgroup_namespace=row['namespaces']['cgroup'],systemd=initial,expected_supplementary_groups=self.credential_baseline['supplementary_groups'],trust=dict(kernel_correct=True,privileged_manager_no_migration_reconfiguration_or_proxy=True),execution_identity=identity,binding=self.binding,initial_proc_status=row['proc_status'],initial_proc_stat=row['proc_stat'])
                    record_sha=publish(self.dir/'security-record.json',record)
                    self.policy=dict(security_record_path=INNER_DIRECTORY+'/security-record.json',security_record_sha256=record_sha,trusted_kernel=True,trusted_privileged_manager=True,binding=self.binding,launch_manifest_sha256=self.manifest_sha256)
                    publish(self.dir/'a-policy.json',self.policy)
                elif row['properties']!=initial:raise ValueError('A actual systemd properties changed')
                self.rows.append(row)
                ready=self.artifact_dir/'a-completion-ready.json'
                if ready.exists():
                    ended=json.loads(ready.read_bytes())
                    if (ended['unit'],ended['run_id'],ended['pid'])!=(self.configuration['unit'],self.configuration['run_id'],int(initial['ExecMainPID'])) or row['monotonic_ns']<ended['after_monotonic']*1e9:
                        raise ValueError('A end handshake identity/time')
                    verify_sources(self.root,self.binding['source_manifest'])
                    while len(self.rows)<3:
                        extra=self.read_actual()
                        if extra is None or extra['properties']!=initial:raise ValueError('A final root security consistency')
                        self.rows.append(extra);row=extra
                    self.end=dict(raw=row['raw'],props=row['properties'],monotonic_ns=row['monotonic_ns'],proc_status=row['proc_status'],proc_stat=row['proc_stat'],namespaces=row['namespaces'])
                    publish(self.dir/'security-end.json',self.end);break
                time.sleep(.02)
        except Exception as exc:self.errors.append(str(exc))
    def finish(self):
        self.done.set()
        if self.thread is not None:self.thread.join(timeout=3)
        if self.thread is not None and self.thread.is_alive():self.errors.append('A root manager join timeout')
        data=dict(launch_manifest=self.manifest,policy=self.policy,security_rows=self.rows,preparation_rows=self.preparation_rows,security_end_record=self.end,errors=self.errors)
        publish(self.dir/'manager-evidence.json',data)
        return data

def wait_immutable(directory,name,seconds=8):
    deadline=time.monotonic()+seconds;path=Path(directory)/name
    while not path.exists():
        if time.monotonic()>deadline:raise ValueError('A manager evidence timeout: '+name)
        time.sleep(.005)
    return immutable(path)
def admit_inner(g,artifact_dir,unit,run_id,profile,directory,manifest_sha256):
    manifest=immutable(Path(directory)/'launch-manifest.json')
    if digest((Path(directory)/'launch-manifest.json').read_bytes())!=manifest_sha256:raise ValueError('A launch manifest digest')
    binding=manifest['binding'];config=manifest['configuration']
    if (binding['unit'],binding['run_id'],binding['profile'])!=(unit,run_id,profile) or binding['configuration_sha256']!=digest(canonical(config)):
        raise ValueError('A launch binding')
    for name,want in binding['source_manifest'].items():
        if digest((Path('/workspace')/name).read_bytes())!=want:raise ValueError('A inner approved source changed')
    identity=g._process_identity(os.getpid())
    g._write_json(Path(artifact_dir)/'a-wrapper-ready.json',dict(unit=unit,run_id=run_id,pid=os.getpid(),start_ticks=identity['start_ticks']))
    policy=wait_immutable(directory,'a-policy.json')
    if policy['binding']!=binding or policy['launch_manifest_sha256']!=manifest_sha256:raise ValueError('A policy/launch binding')
    return policy

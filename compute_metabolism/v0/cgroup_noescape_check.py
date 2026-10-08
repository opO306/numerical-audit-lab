"""Independent TEST_ONLY checker: intentionally no import of a_impl or base guard."""
import hashlib,json
from pathlib import Path

def must(ok,msg):
    if not ok:raise ValueError(msg)


# Independent retained-raw parsers. No producer or base-guard parser imports.
def _same(value, expected, message):
    must(json.dumps(value,sort_keys=True,allow_nan=False)==json.dumps(expected,sort_keys=True,allow_nan=False),message)

def _raw_text(raw):
    must(type(raw) is str and raw.isascii() and 0<len(raw)<=65536,'raw text missing, non-ASCII, or exceeds bound')
    return raw

def _raw_uint(raw):
    token=_raw_text(raw).strip()
    must(token.isdecimal() and len(token)<=20 and str(int(token))==token,'noncanonical unsigned integer')
    value=int(token)
    must(value<=18446744073709551615,'unsigned integer exceeds 64-bit width')
    return value

def _raw_table(raw,required):
    rows={}
    for line in _raw_text(raw).splitlines():
        parts=line.split()
        must(len(parts)==2,'counter row must have exactly two columns')
        key,token=parts
        must(key and key[0].isalpha() and all(c.isalnum() or c=='_' for c in key) and key not in rows,'invalid or duplicate counter name')
        rows[key]=_raw_uint(token)
    must(set(required)<=rows.keys(),'required counter row absent')
    return rows

def _raw_cpus(raw):
    values=[]
    for term in _raw_text(raw).strip().split(','):
        ends=term.split('-');must(1<=len(ends)<=2,'invalid CPU interval')
        lo=_raw_uint(ends[0]);hi=lo if len(ends)==1 else _raw_uint(ends[1])
        must(lo<=hi and hi<=1048575 and hi-lo<4096,'CPU interval invalid or unbounded')
        values.extend(range(lo,hi+1));must(len(values)<=4096,'CPU set exceeds bound')
    must(len(values)==len(set(values)),'CPU set contains duplicates')
    return sorted(values)

def _raw_quota(raw):
    fields=_raw_text(raw).split();must(len(fields)==2,'cpu.max column count')
    quota=None if fields[0]=='max' else _raw_uint(fields[0]);period=_raw_uint(fields[1])
    must(period>0 and (quota is None or quota>0),'nonpositive CPU quota or period')
    return quota,period

def _raw_memory(raw):
    return None if _raw_text(raw).strip()=='max' else _raw_uint(raw)

def _snapshot_raw(snapshot,quiescent=True):
    raw=snapshot['raw'];leaf=snapshot['epoch']['path']
    must(leaf.startswith('/sys/fs/cgroup/system.slice/') and len(leaf.split('/'))==6 and leaf.rsplit('/',1)[1] not in ('','.','..'),'invalid cgroup leaf path')
    roots=[leaf,'/sys/fs/cgroup/system.slice','/sys/fs/cgroup']
    _same(snapshot['cpu_stat'],_raw_table(raw['cpu.stat'],('usage_usec','user_usec','system_usec')),'cpu.stat raw/parsed mismatch')
    _same(snapshot['memory_events'],_raw_table(raw['memory.events'],('oom','oom_kill')),'memory.events raw/parsed mismatch')
    for file,field in [('memory.current','memory_current'),('memory.peak','memory_peak')]:
        _same(snapshot[field],_raw_uint(raw[file]),file+' raw/parsed mismatch')
    cpus=_raw_cpus(raw['cpuset.cpus.effective']);_same(snapshot['cpus'],cpus,'cpuset raw/parsed mismatch');must(cpus==[0,1],'fixed 2c CPU set mismatch')
    members=[]
    for line in _raw_text(raw['cgroup.procs']).splitlines():
        pid=_raw_uint(line);must(0<pid<=2147483647,'invalid raw cgroup PID');members.append(pid)
    must(len(members)==len(set(members)),'duplicate raw cgroup PID')
    if quiescent:
        _same(snapshot['pids'],sorted(members),'quiescent raw cgroup membership mismatch')
        _same(snapshot['enumerated_pids'],sorted(members),'quiescent enumerated membership mismatch')
    events=_raw_table(raw['cgroup.events'],('populated','frozen'))
    must(events['populated'] in (0,1) and events['frozen'] in (0,1),'invalid cgroup event value')
    if quiescent:must(events['populated']==1 and events['frozen']==0,'wrapper-only cgroup event mismatch')
    if 'cgroup_events' in snapshot:_same(snapshot['cgroup_events'],events,'cgroup.events raw/parsed mismatch')
    for field,file,want in [('memory','memory.max',4294967296),('swap','memory.swap.max',0)]:
        limits=snapshot[field];chain=limits['ancestors'];must(type(chain) is list and len(chain)==3,'incomplete memory ancestor chain')
        rebuilt=[];finite=[]
        for index,(entry,directory) in enumerate(zip(chain,roots)):
            filename=directory+'/'+file;must(entry['path']==filename,'memory ancestor order/path mismatch')
            if entry['raw'] is None:
                must(index==2,'memory ancestor value missing below root')
                expected={'path':filename,'raw':None,'missing_at_root':True}
            else:
                value=_raw_memory(entry['raw']);expected={'path':filename,'raw':entry['raw'],'bytes':value}
                if value is not None:finite.append(value)
            _same(entry,expected,'memory ancestor raw/parsed mismatch');rebuilt.append(expected)
        effective=min(finite) if finite else None
        _same(limits,{'effective_bytes':effective,'ancestors':rebuilt,'scan_root':'/sys/fs/cgroup'},'derived memory limit mismatch')
        must(raw[file]==chain[0]['raw'],'leaf raw memory limit differs from ancestor record')
        must(_raw_memory(raw[file])==want and effective==want,'fixed memory/swap limit mismatch')
    cpu=snapshot['cpu_max'];chain=cpu['ancestors'];must(type(chain) is list and len(chain)==3,'incomplete CPU ancestor chain')
    rebuilt=[];known=[];finite=[]
    for index,(entry,directory) in enumerate(zip(chain,roots)):
        filename=directory+'/cpu.max';must(entry['path']==filename,'CPU ancestor order/path mismatch')
        if entry['raw'] is None:
            must(index in (0,2),'CPU ancestor missing below root')
            expected={'path':filename,'raw':None,'missing_at_root':index==2}
        else:
            quota,period=_raw_quota(entry['raw']);expected={'path':filename,'raw':entry['raw'],'quota_usec':quota,'period_usec':period};known.append(expected)
            if quota is not None:finite.append(expected)
        _same(entry,expected,'CPU ancestor raw/parsed mismatch');rebuilt.append(expected)
    must(bool(known),'no effective CPU quota authority');nearest=known[0]
    derived={'source':nearest['path'],'raw':nearest['raw'],'quota_usec':nearest['quota_usec'],'period_usec':nearest['period_usec'],'unlimited':not finite,'finite_ancestors':finite,'ancestors':rebuilt,'scan_root':'/sys/fs/cgroup'}
    _same(cpu,derived,'derived CPU quota/source mismatch');must(raw['cpu.max']==nearest['raw'],'snapshot cpu.max raw differs from effective source')
    must(not finite,'fixed 2c profile has a finite ancestor quota')

def _event_raw(event,owned):
    samples=event['process_samples']
    must([v['kind'] for v in samples]==['stat','stat','stat','cgroup','stat','cgroup'],'bound process witness sample sequence incomplete')
    identities=[];cgroups=[]
    for sample in samples:
        raw=_raw_text(sample['raw'])
        if sample['kind']=='cgroup':
            must(raw in ('0::'+owned,'0::'+owned+'\n'),'retained raw process outside owned cgroup')
            cgroups.append(raw);continue
        opening=raw.find(' (');closing=raw.rfind(')')
        must(opening>0 and closing>opening,'invalid process stat delimiters')
        pid=_raw_uint(raw[:opening]);fields=raw[closing+1:].split()
        must(len(fields)>=20 and len(fields[0])==1 and fields[0].isalpha(),'invalid process stat fields')
        start=_raw_uint(fields[19]);ppid=_raw_uint(fields[1]);must(pid<=2147483647 and ppid<=2147483647,'process stat PID width')
        ident={'pid':pid,'start_ticks':str(start),'state':fields[0]}
        must(pid==event['pid'] and ident['start_ticks']==event['first']['start_ticks'],'raw process birth mismatch')
        if 'identity' in sample:_same(sample['identity'],ident,'embedded process identity differs from raw stat')
        if 'ppid' in sample:_same(sample['ppid'],ppid,'embedded parent PID differs from raw stat')
        identities.append(ident)
    _same(event['cgroups'],cgroups,'duplicated process cgroup differs from retained raw')
    _same(event['first'],identities[2],'first event identity differs from corresponding raw stat')
    _same(event['second'],identities[3],'second event identity differs from corresponding raw stat')

def check(artifact_dir,policy,guard_result=None,outer=None):
    try:
        proof=json.loads((Path(artifact_dir)/'a_security_proof.json').read_text())
        return check_proof(proof,policy,guard_result,outer)
    except Exception as exc:return dict(status='REFUSED',error=str(exc))

def check_proof(proof,policy,guard_result=None,outer=None):
    try:
        must(proof['schema']=='task9-a-proof-v1' and proof['status']=='CONDITIONAL_GROUP_PROOF' and proof['error'] is None,'producer refused or schema')
        must(proof['policy']==policy,'independent policy differs')
        must(policy.get('trusted_kernel') is True and policy.get('trusted_privileged_manager') is True,'trust not approved')
        raw=proof['security_record_raw'];r=json.loads(raw)
        must(hashlib.sha256(raw.encode()).hexdigest()==policy['security_record_sha256'] and r==proof['security_record'],'frozen security record binding')
        must(r['schema']=='task9-ab-security-v1','record schema')
        must(r['trust']['kernel_correct'] is True and r['trust']['privileged_manager_no_migration_reconfiguration_or_proxy'] is True,'record trust absent')
        expected={'ControlGroup':r['control_group'],'User':'1000','Group':'1003','Delegate':'no','NoNewPrivileges':'yes','CapabilityBoundingSet':'','AmbientCapabilities':'','ProtectControlGroups':'yes','RestrictNamespaces':'yes','RestrictSUIDSGID':'yes'}
        must(r['control_group']=='/system.slice/'+r['unit'] and all(str(r['systemd'].get(k))==v for k,v in expected.items()),'effective manager property mismatch')
        groups_expected=r.get('expected_supplementary_groups')
        must(isinstance(groups_expected,list) and all(type(gid) is int and 0<gid<4294967295 for gid in groups_expected),'frozen supplementary groups missing or malformed')
        must(groups_expected==sorted(set(groups_expected)),'frozen group order or duplicates')
        must(_raw_cpus(r['systemd']['AllowedCPUs'])==[0,1] and _raw_cpus(r['systemd']['EffectiveCPUs'])==[0,1],'frozen manager CPU resource mismatch')
        must(_raw_uint(r['systemd']['MemoryMax'])==4294967296 and _raw_uint(r['systemd']['MemorySwapMax'])==0,'frozen manager memory resource mismatch')
        snaps=proof['snapshots'];must(len(snaps)>=3,'baseline/during/final proof missing')
        first=None;last_time=-1
        for row in snaps:
            must(row['monotonic_ns']>=last_time,'proof time reversed');last_time=row['monotonic_ns'];s=row['evidence'];v=s['status']
            must(v['Uid'].split()==['1000']*4 and v['Gid'].split()==['1003']*4,'execution credential mismatch')
            actual_groups=v['Groups'].split()
            must(all(token.isascii() and token.isdecimal() and str(int(token))==token and 0<int(token)<4294967295 for token in actual_groups),'malformed observed supplementary groups')
            actual_groups=[int(token) for token in actual_groups]
            must(actual_groups==sorted(set(actual_groups)) and actual_groups==groups_expected,'observed supplementary groups changed or differ from root binding')
            for name in ['CapInh','CapPrm','CapEff','CapBnd','CapAmb']:must(int(v[name],16)==0,'capability present')
            must(v['NoNewPrivs']=='1' and v['Seccomp']=='2','filter absent')
            must(s['boot_id']==r['boot_id'] and s['cgroup'].strip()=='0::'+r['control_group'],'cgroup or boot mismatch')
            must(s['namespaces']['user']==r['host_user_namespace'] and s['namespaces']['cgroup']==r['expected_cgroup_namespace'],'namespace mismatch')
            must(bool(s['mounts']),'mounts missing')
            for m in s['mounts']:must(m['fstype']=='cgroup2' and m['root']=='/' and m['point']=='/sys/fs/cgroup' and 'ro' in m['options'] and 'rw' not in m['options'],'writable or hidden cgroup hierarchy')
            must(bool(s['permissions']) and not s['control_fds'],'permission inventory or inherited control descriptor')
            required=set()
            for directory in ['/sys/fs/cgroup','/sys/fs/cgroup/system.slice','/sys/fs/cgroup'+r['control_group']]:required.update([directory,directory+'/cgroup.procs',directory+'/cgroup.threads',directory+'/cgroup.subtree_control'])
            must(required <= {item['path'] for item in s['permissions']},'incomplete ancestor permission inventory')
            for item in s['permissions']:must(item['uid']==0 and (item['mode'] & 0o022)==0 and not item['acl'] and item['writable'] is False,'migration permission')
            must(s['epoch']['path']=='/sys/fs/cgroup'+r['control_group'] and s['epoch']['boot_id']==r['boot_id'],'epoch binding')
            stable={k:s[k] for k in ['namespaces','uid_map','gid_map','boot_id','cgroup','mounts','permissions','epoch']}
            stable['supplementary_groups']=actual_groups
            if first is None:first=stable
            must(stable==first,'security invariant changed')
        unknown=0;wrapper_events=[]
        for event in proof['events']:
            must(type(event['pid']) is int and event['pid']>0 and 0<=event['security_index']<len(snaps),'event identity or security index')
            if event['status']=='IDENTITY_UNKNOWN':
                must(event['identity'] is None and event['individual_exit_proven'] is False,'fabricated exit');unknown+=1
            else:
                must(event['status']=='BOUND_IDENTITY','unknown event status')
                _event_raw(event,r['control_group'])
                a,b=event['first'],event['second']
                raw_stats=[entry['raw'] for entry in event['process_samples'] if entry['kind']=='stat']
                must(len(raw_stats)>=2,'raw stat binding absent')
                for raw_stat in raw_stats:
                    fields=raw_stat.rsplit(')',1)[1].split()
                    must(int(raw_stat.split(' ',1)[0])==event['pid'] and fields[19]==a['start_ticks'],'raw stat PID/start mismatch')
                if event['pid']==proof['wrapper_pid']:wrapper_events.append(event)
                must(a['pid']==b['pid']==event['pid'] and a['start_ticks']==b['start_ticks'],'PID reuse')
                must(len(event['cgroups'])==2,'membership evidence absent')
                for cg in event['cgroups']:
                    must(cg.strip()=='0::'+r['control_group'],'observed membership outside approved group')
        must(wrapper_events and wrapper_events[0]['security_index']==0,'wrapper baseline evidence missing')
        must(all(e['first']['start_ticks']==wrapper_events[0]['first']['start_ticks'] for e in wrapper_events),'wrapper PID reused')
        base=dict(scope='CONDITIONAL_GROUP_ACCOUNTING_ONLY',unknown_pid_observations=unknown,individual_lifetime_completeness='NOT_CLAIMED',external_manager_interference_detection='NOT_CLAIMED; explicit trusted noninterference premise')
        if guard_result is None or outer is None:return dict(status='CONDITIONAL_GROUP_PROOF',**base)
        g=guard_result;o=outer
        must(g['measurement_valid'] is True and g['outcome']=='GUARD_COMPLETE' and g['child_returncode']==0,'guard not successful')
        must(not g.get('error') and not g.get('cleanup_errors') and not g.get('final_errors'),'guard errors')
        must(g['containment']['remaining_pids']==[],'residual processes')
        wrapper=wrapper_events[0]['first']
        must(g['wrapper_identity']['pid']==wrapper['pid'] and g['wrapper_identity']['start_ticks']==wrapper['start_ticks'],'wrapper guard identity')
        must(g['after']['pids']==[wrapper['pid']],'final cgroup membership not wrapper-only')
        must(g['profile']=='2c','only selected 2c profile supported')
        before,after=g['before'],g['after']
        for endpoint in (before,after):_snapshot_raw(endpoint,quiescent=True)
        must(before['epoch']==after['epoch']==first['epoch'],'measurement epoch')
        must(after['monotonic_seconds']>=before['monotonic_seconds'],'measurement clock')
        for name,value in before['cpu_stat'].items():must(after['cpu_stat'][name]>=value,'CPU counter reset')
        must(after['memory_peak']>=before['memory_peak'],'memory counter reset')
        for name,value in before['memory_events'].items():must(after['memory_events'][name]>=value,'memory event reset')
        for snap in (before,after):
            must(snap['cpus']==[0,1] and snap['memory']['effective_bytes']==4294967296 and snap['swap']['effective_bytes']==0,'resource envelope')
            must(int(snap['raw']['memory.max'])==4294967296 and int(snap['raw']['memory.swap.max'])==0,'leaf limits')
        must(o.get('outcome')=='GUARD_COMPLETE' and o.get('measurement_valid') is True,'outer execution failed or measurement invalid')
        for name in ('run_id','unit','profile'):
            must(isinstance(g.get(name),str) and bool(g[name]) and o.get(name)==g[name],'outer/guard identity mismatch: '+name)
        must(g['unit']==r['unit'],'guard frozen unit mismatch')
        for name in ('error','errors','cleanup_errors','terminal_errors','final_errors','timeout','timed_out','timeout_error','outer_timeout_proved','timeout_observed_monotonic'):
            must(not o.get(name),'outer failure: '+name)
        must(o.get('returncode')==0,'outer launcher returncode')
        attempts=o.get('cleanup_attempts',[])
        must(isinstance(attempts,list),'cleanup attempts invalid')
        for attempt in attempts:
            must(isinstance(attempt,dict),'cleanup attempt invalid')
            for name in ('error','errors','cleanup_errors','terminal_errors','final_errors'):
                must(not attempt.get(name),'cleanup attempt failure: '+name)
            if 'returncode' in attempt:must(attempt['returncode']==0,'cleanup attempt returncode')
        must(o.get('before')==before and o.get('after')==after,'outer/guard measurement disagreement')
        recomputed={}
        for name in ('usage_usec','user_usec','system_usec','nr_periods','nr_throttled','throttled_usec'):
            if name not in before['cpu_stat'] and name not in after['cpu_stat'] and name not in ('usage_usec','user_usec','system_usec'):continue
            a,b=before['cpu_stat'][name],after['cpu_stat'][name]
            must(type(a) is int and type(b) is int and 0<=a<=b,'invalid CPU counter')
            recomputed[name]=b-a
        recomputed['cpu_seconds']=recomputed['usage_usec']/1000000
        must(g.get('delta')==recomputed and o.get('delta')==recomputed,'measurement delta does not match raw counters')
        for pid in before.get('process_identities',{}).keys() & after.get('process_identities',{}).keys():
            must(before['process_identities'][pid]['start_ticks']==after['process_identities'][pid]['start_ticks'],'PID reuse between guard snapshots')
        must(o.get('terminal') is True and o.get('launcher_reaped') is True,'outer cleanup missing')
        must(o.get('security_end_unchanged') is True,'external end property comparison missing')
        end=o['security_end_record'];parsed={}
        must(isinstance(end['raw'],str) and bool(end['raw']),'end raw systemctl evidence missing')
        for line in end['raw'].splitlines():
            must('=' in line,'invalid end systemctl raw line')
            key,value=line.split('=',1)
            must(key and key not in parsed,'duplicate end systemctl property')
            parsed[key]=value
        must(parsed==end['props']==r['systemd'],'actual end properties differ from frozen initial properties')
        must(parsed['Id']==g['unit'] and parsed['ExecMainPID']==str(wrapper['pid']),'end unit/wrapper binding')
        must(type(end['monotonic_ns']) is int and end['monotonic_ns']>=after['monotonic_seconds']*1000000000,'end evidence predates final measurement')
        return dict(status='PASS',**base)
    except Exception as exc:return dict(status='REFUSED',error=str(exc))


# Formal path adds execution binding; historical TEST_ONLY evidence stays separate.
def _canonical(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)+'\n').encode('ascii')

def _strict_json(raw):
    def pairs(rows):
        out={}
        for k,v in rows:
            must(k not in out,'duplicate JSON key');out[k]=v
        return out
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('nonfinite JSON')))

def _manager_properties(row):
    parsed={}
    for line in _raw_text(row['raw']).splitlines():
        must('=' in line,'systemctl property syntax');key,value=line.split('=',1)
        must(key and key not in parsed,'duplicate systemctl property');parsed[key]=value
    _same(parsed,row.get('properties',row.get('props')),'root systemctl raw/parsed mismatch')
    return parsed

def check_guard(artifact_dir,policy,inner,outer):
    try:
        folder=Path(artifact_dir);raw=(folder/'a_security_proof.json').read_bytes();proof=_strict_json(raw)
        must(hashlib.sha256(raw).hexdigest()==inner['a_proof_sha256'],'A proof file hash')
        _same(inner['a_policy'],policy,'inner policy binding')
        result=check_proof(proof,policy,inner,outer)
        must(result['status']=='PASS','base independent A check: '+str(result))
        binding=policy['binding'];manager=outer['a_manager'];launch=manager['launch_manifest']
        must(launch['schema']=='cm-a-launch-v1' and not manager['errors'],'root launch/schema/errors')
        _same(launch['binding'],binding,'root launch policy binding')
        _same(proof['security_record']['binding'],binding,'root security record policy binding')
        must(policy['launch_manifest_sha256']==hashlib.sha256(_canonical(launch)).hexdigest(),'root launch manifest hash')
        must(binding['profile']=='2c' and binding['scope'] in ('TEST_ONLY','LIVE'),'formal 2c scope')
        for key in ('run_id','unit','profile'):must(binding[key]==inner[key]==outer[key],'formal execution binding '+key)
        must(type(binding['authority_id']) is str and bool(binding['authority_id']),'authority absent')
        approval=binding['trust_approval']
        must(type(approval['approved_by']) is str and bool(approval['approved_by']) and approval['scope']==binding['scope'] and approval['kernel_correct'] is True and approval['privileged_manager_no_migration_reconfiguration_or_proxy'] is True,'explicit scoped trust approval')
        must(approval['noninterference_scope']=='correct_kernel_and_approved_privileged_manager_noninterference_for_this_run','explicit noninterference scope')
        if binding['scope']=='LIVE':
            epoch=binding['source_epoch'];must(type(epoch) is dict and epoch['source_binding']==binding['v1_source_binding'],'LIVE V1 source epoch binding')
        manifest=binding['source_manifest']
        must(type(manifest) is dict and bool(manifest) and all(type(k) is str and type(v) is str and len(v)==64 and all(c in '0123456789abcdef' for c in v) for k,v in manifest.items()),'source manifest absent')
        must(hashlib.sha256(_canonical(manifest)).hexdigest()==binding['source_binding'],'source manifest binding')
        must(hashlib.sha256(_canonical(launch['configuration'])).hexdigest()==binding['configuration_sha256'],'configuration binding')
        for key in ('run_id','unit','profile'):must(launch['configuration'][key]==binding[key],'configuration identity')
        must(launch['identity']=={'uid':1000,'gid':1003},'launch credentials')
        credentials=binding['credential_baseline']
        must(credentials['uid']==1000 and credentials['gid']==1003 and type(credentials['nss_primary_gid']) is int and 0<credentials['nss_primary_gid']<4294967295 and type(credentials['nss_user']) is str and bool(credentials['nss_user']),'root NSS credential baseline')
        _same(credentials['supplementary_groups'],proof['security_record']['expected_supplementary_groups'],'root NSS expected supplementary groups')
        running_raw=(folder/'guard-cgroup-running.jsonl').read_bytes()
        locator=outer['running_file'];must(locator['path']=='guard-cgroup-running.jsonl' and locator['sha256']==hashlib.sha256(running_raw).hexdigest(),'running file hash/path')
        rows=[_strict_json(line) for line in running_raw.splitlines()]
        _same(rows,inner['running_snapshots'],'all retained running snapshots required')
        chain=[];previous_hash=None
        for row in rows:
            digest=hashlib.sha256((json.dumps(row,sort_keys=True,allow_nan=False)+'\n').encode()).hexdigest()
            chain.append(dict(previous=previous_hash,sha256=digest));previous_hash=digest
        _same(chain,inner['running_snapshot_chain'],'running snapshot hash chain incomplete')
        sequence=[inner['before']]+rows+[inner['after']]
        previous=None
        for snapshot in sequence:
            _snapshot_raw(snapshot,quiescent=False)
            must(snapshot['epoch']==inner['before']['epoch'],'running cgroup epoch drift')
            clock=snapshot['monotonic_seconds'];must(type(clock) in (int,float) and clock>=0,'running clock')
            if previous:
                must(clock>=previous['monotonic_seconds'],'running time reversal')
                for field in ('cpu_stat','memory_events'):
                    must(set(snapshot[field])==set(previous[field]),'running counter coverage drift')
                    must(all(snapshot[field][k]>=v for k,v in previous[field].items()),'running counter reset')
                must(snapshot['memory_peak']>=previous['memory_peak'],'running memory peak reset')
            must(snapshot['memory_events']['oom']==0 and snapshot['memory_events']['oom_kill']==0,'running OOM')
            must(snapshot['memory_current']<=4294967296 and snapshot['memory_peak']<=4294967296,'running memory envelope')
            previous=snapshot
        # Every process witness must be located at the collector security sample.
        security=proof['snapshots'];events=proof['events']
        must(len(security)==2*len(sequence)+1,'exact security coverage of resource snapshots missing')
        must(security[-1]['monotonic_ns']>=sequence[-1]['acquisition_end_ns'],'final security postdates final snapshot')
        consumed_events=[]
        for position,snap in enumerate(sequence):
            begin=snap['acquisition_begin_ns'];end=snap['acquisition_end_ns']
            must(type(begin) is int and type(end) is int and begin<=snap['monotonic_seconds']*1000000000<=end,'snapshot acquisition interval')
            index=snap['process_security_index'];end_index=snap['process_security_end_index']
            must(type(index) is int and type(end_index) is int and index==2*position and end_index==index+1,'snapshot security index/order')
            must(begin<=security[index]['monotonic_ns']<=security[end_index]['monotonic_ns']<=end,'snapshot security acquisition link')
            linked=[e for e in events if e['security_index']==index]
            enumerated=snap['enumerated_pids'];must(type(enumerated) is list and len(enumerated)==len(set(enumerated)),'snapshot PID enumeration')
            must(sorted(e['pid'] for e in linked)==sorted(enumerated),'snapshot PID/event coverage')
            identities={};observations={}
            for event in linked:
                consumed_events.append(event)
                pid=str(event['pid'])
                if event['status']=='BOUND_IDENTITY':
                    _event_interval(event['process_samples'],security[index]['monotonic_ns'],security[end_index]['monotonic_ns'])
                    identities[pid]=event['second']
                    observations[pid]=dict(status='group_accounted_bound_identity',identity=event['second'],individual_exit_proven=False)
                    if event['pid'] in (inner['wrapper_identity']['pid'],inner['child_identity']['pid']):
                        strict=event['required_individual_evidence']
                        strict_observation=strict['observations'][pid]
                        must(strict_observation['status'] in ('stable','exited_during_sample'),'strict protected observation status')
                        if strict_observation['status']=='stable':
                            must(pid in strict['identities'] and strict['identities'][pid]==strict_observation['identity'] and all(strict['identities'][pid][k]==event['second'][k] and strict_observation['identity'][k]==event['second'][k] for k in ('pid','start_ticks')),'strict protected individual identity absent')
                        else:
                            exit_proof=strict_observation['exit_evidence'];terminal=exit_proof['terminal_identity']
                            must(exit_proof['basis']=='BOUND_PROCESS_PIDFD_AND_TERMINAL_OWNED_CGROUP' and terminal['pid']==event['pid'] and terminal['start_ticks']==event['second']['start_ticks'] and terminal['state'] in ('Z','X') and len(exit_proof['pidfd_events'])==1,'strict protected terminal process proof')
                            fd,mask=exit_proof['pidfd_events'][0]
                            must(type(fd) is int and fd>=0 and type(mask) is int and mask&1 and not mask&~17,'strict protected pidfd readiness mask')
                            terminal_stats=[sample for sample in exit_proof['process_samples'] if sample['kind']=='stat']
                            parsed_terminal=_parse_stat(terminal_stats[-1]['raw'])
                            _same(terminal,dict(pid=parsed_terminal[0],start_ticks=parsed_terminal[1],state=parsed_terminal[3]),'strict terminal raw state/identity mismatch')
                            must(exit_proof['terminal_cgroup'].strip()=='0::'+proof['security_record']['control_group'] and exit_proof['process_samples'][-1]['kind']=='cgroup' and exit_proof['process_samples'][-1]['raw']==exit_proof['terminal_cgroup'],'strict terminal final raw cgroup')
                            for membership_name in ('membership1','membership2'):_membership_proof(exit_proof[membership_name],snap['epoch'],security[index]['monotonic_ns'],security[end_index]['monotonic_ns'])
                            _event_interval(exit_proof['process_samples'],security[index]['monotonic_ns'],security[end_index]['monotonic_ns'])
                            for raw_sample in exit_proof['process_samples']:
                                if raw_sample['kind']=='stat':
                                    parsed=_parse_stat(raw_sample['raw']);must(parsed[0]==event['pid'] and parsed[1]==terminal['start_ticks'],'strict protected terminal raw birth')
                                else:must(raw_sample['raw'].strip()=='0::'+proof['security_record']['control_group'],'strict protected terminal raw cgroup')
                else:
                    must(event['pid'] not in (inner['wrapper_identity']['pid'],inner['child_identity']['pid']),'required individual identity unknown')
                    observations[pid]=dict(status='group_accounted_identity_unknown',identity=None,individual_exit_proven=False,basis='FROZEN_CONDITIONAL_NOESCAPE')
            for pid in snap['pids']:
                if pid not in enumerated:observations[str(pid)]=dict(status='appeared_during_sample',identity=None,individual_exit_proven=False)
            _same(snap['process_identities'],identities,'snapshot event identity binding')
            _same(snap['process_observations'],observations,'snapshot process observation binding')
            must(str(proof['wrapper_pid']) in identities,'snapshot wrapper identity absent')
        must(len(consumed_events)==len(events),'unlinked process event')
        child=inner['child_individual_witness'];identity=child['identity']
        must(identity['pid']==inner['child_identity']['pid'] and identity['start_ticks']==inner['child_identity']['start_ticks'],'primary child birth binding')
        samples=child['process_samples'];must([v['kind'] for v in samples]==['stat','stat','stat','cgroup'],'primary child initial witness incomplete')
        _event_interval(samples,inner['before']['acquisition_end_ns'],inner['after']['acquisition_begin_ns'])
        must(child['cgroup'].strip()=='0::'+proof['security_record']['control_group'],'primary child cgroup')
        for sample in samples:
            if sample['kind']=='cgroup':must(sample['raw']==child['cgroup'],'primary child raw cgroup')
            else:
                parsed=_parse_stat(sample['raw'])
                must(parsed[0]==identity['pid'] and parsed[1]==identity['start_ticks'] and parsed[2]==inner['wrapper_identity']['pid'],'primary child raw birth/parent')
                _same(sample['identity'],dict(pid=parsed[0],start_ticks=parsed[1],state=parsed[3]),'primary child parsed stat mismatch')
        root_rows=manager['security_rows'];must(len(root_rows)>=3,'root baseline/during/end missing')
        must(root_rows[0]['monotonic_ns']<=inner['before']['monotonic_seconds']*1000000000 and root_rows[-1]['monotonic_ns']>=inner['after']['monotonic_seconds']*1000000000,'root security time coverage')
        baseline=proof['security_record']['systemd'];last=-1;wrapper=inner['wrapper_identity']
        for row in root_rows:
            must(type(row['monotonic_ns']) is int and row['monotonic_ns']>=last,'root security time reversal');last=row['monotonic_ns']
            props=_manager_properties(row);_same(props,baseline,'root security properties changed')
            must(props['Id']==binding['unit'] and props['MainPID']==props['ExecMainPID']==str(wrapper['pid']),'actual unit process binding')
            status={}
            for line in _raw_text(row['proc_status']).splitlines():
                if ':' in line:
                    k,v=line.split(':',1);must(k not in status,'duplicate process status field');status[k]=v.strip()
            must(status['Uid'].split()==['1000']*4 and status['Gid'].split()==['1003']*4 and status['NoNewPrivs']=='1' and status['Seccomp']=='2' and _raw_uint(status['Pid'])==wrapper['pid'],'root observed process credentials/filter/PID')
            must(sorted(int(x) for x in status['Groups'].split())==proof['security_record']['expected_supplementary_groups'],'root supplementary group binding')
            must(all(int(status[k],16)==0 for k in ('CapInh','CapPrm','CapEff','CapBnd','CapAmb')),'root observed capability')
            stat=_raw_text(row['proc_stat']);must(int(stat.split(' ',1)[0])==wrapper['pid'] and stat.rsplit(')',1)[1].split()[19]==wrapper['start_ticks'],'root observed wrapper birth')
            must(row['namespaces']['user']==proof['security_record']['host_user_namespace'] and row['namespaces']['cgroup']==proof['security_record']['expected_cgroup_namespace'],'root observed namespace')
            _same(row['namespaces'],security[0]['evidence']['namespaces'],'root observed complete namespace binding')
        return dict(result,status='A_INDEPENDENT_CHECK_PASS',configuration_sha256=binding['configuration_sha256'],source_binding=binding['source_binding'],proof_sha256=hashlib.sha256(raw).hexdigest(),running_sha256=locator['sha256'],checked_running_snapshots=len(rows),binding=binding)
    except Exception as exc:return dict(status='REFUSED',error=str(exc))


def _event_interval(samples,begin,end):
    previous=begin
    for sample in samples:
        a=sample['begin_ns'];b=sample['end_ns']
        must(type(a) is int and type(b) is int and previous<=a<=b<=end,'process sample acquisition interval')
        previous=b

def _parse_stat(raw):
    raw=_raw_text(raw);opening=raw.find(' (');closing=raw.rfind(')');must(opening>0 and closing>opening,'process stat delimiters')
    fields=raw[closing+1:].split();must(len(fields)>=20,'process stat fields')
    return _raw_uint(raw[:opening]),str(_raw_uint(fields[19])),_raw_uint(fields[1]),fields[0]


def _membership_proof(record,epoch,begin,end):
    must(record['epoch']==epoch and begin<=record['begin_ns']<=record['end_ns']<=end,'strict terminal membership acquisition epoch/time')
    files=record['files'];must(type(files) is list and 0<len(files)<=1024,'strict terminal membership inventory')
    pids=set();paths=[]
    for row in files:
        path=row['path'];must(path==epoch['path']+'/cgroup.procs' or (path.startswith(epoch['path']+'/') and path.endswith('/cgroup.procs') and '..' not in path.split('/')),'strict terminal membership path')
        must(record['begin_ns']<=row['begin_ns']<=row['end_ns']<=record['end_ns'],'strict terminal membership read interval')
        must(type(row['device']) is int and type(row['inode']) is int and row['device']==epoch['device'],'strict terminal membership inode identity')
        paths.append(path)
        for token in _raw_text(row['raw']).split():
            value=_raw_uint(token);must(0<value<=2147483647,'strict terminal membership PID');pids.add(value)
    must(paths==sorted(set(paths)),'strict terminal membership inventory order')
    _same(record['pids'],sorted(pids),'strict terminal raw membership PID binding')

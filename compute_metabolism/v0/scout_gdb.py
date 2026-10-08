"""GDB-only bounded TEST_ONLY scout; no Gala imports or certified state."""
import ctypes,json,mmap,os,resource,sys,hashlib
from pathlib import Path
import gdb
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from verified_driver.v1 import native_evex_capture as cap
from compute_metabolism.v0.scout import NOP_PC,BASE,XGETBV_CODE,save

def cpus(targets):
    samples=[];old=os.sched_getaffinity(0)
    code=bytes.fromhex(cap.CPUID_CODE)
    try:
        with mmap.mmap(-1,len(code),prot=mmap.PROT_READ|mmap.PROT_WRITE|mmap.PROT_EXEC) as page:
            page.write(code);addr=ctypes.addressof(ctypes.c_char.from_buffer(page))
            call=ctypes.CFUNCTYPE(None,ctypes.c_uint32,ctypes.c_uint32,ctypes.POINTER(ctypes.c_uint32))(addr)
            for cpu in targets:
                os.sched_setaffinity(0,{cpu});leaves={}
                for leaf in [0,1,7,13]:
                    data=(ctypes.c_uint32*4)();call(leaf,0,data);leaves[str(leaf)]=dict(zip(['eax','ebx','ecx','edx'],map(int,data)))
                xcr0=None
                if leaves['1']['ecx']&(1<<27):
                    xcode=bytes.fromhex(XGETBV_CODE)
                    with mmap.mmap(-1,len(xcode),prot=mmap.PROT_READ|mmap.PROT_WRITE|mmap.PROT_EXEC) as xpage:
                        xpage.write(xcode);xaddr=ctypes.addressof(ctypes.c_char.from_buffer(xpage));xcall=ctypes.CFUNCTYPE(ctypes.c_uint64)(xaddr)
                        try:xcr0=int(xcall())
                        finally:del xcall
                samples.append(dict(cpu=cpu,leaves=leaves,xcr0=xcr0))
            del call
    finally:os.sched_setaffinity(0,old)
    return samples

def fields(frame):
    names=(*cap.GPRS,'eflags','mxcsr','fs_base','gs_base',*('k'+str(i) for i in range(8)),*cap.SELECTORS,*cap.FP_SCALARS,*('st'+str(i) for i in range(8)),*('zmm'+str(i) for i in range(32)))
    out={}
    for name in names:
        v=frame.read_register(name)
        if v.is_optimized_out is not False:raise ValueError('optimized register: '+name)
        out[name]=dict(type_name=str(v.type),type_code=v.type.code,width_bytes=v.type.sizeof,raw_hex=bytes(v.bytes).hex())
    return out

def main():
    config=json.loads(Path(os.environ['CPU_SCOUT_CONFIG']).read_bytes());policy=config['policy'];out=dict(
        schema='CPU_SCOUT_GDB_RAW_V1',Gala=False,test_only=True,gdb_version=gdb.VERSION,
        cpuid_code_hex=cap.CPUID_CODE,xgetbv_code_hex=XGETBV_CODE,uid=os.getuid(),gid=os.getgid(),
        cwd=os.getcwd(),affinity=sorted(os.sched_getaffinity(0)),rlimit_as=list(resource.getrlimit(resource.RLIMIT_AS)),unknown=[])
    started=False
    try:
        out['cpu_samples']=cpus(policy['cpus'])
        from compute_metabolism.v0.scout_check import cpu
        cpu(out['cpu_samples'],policy) # never execute unsupported fixture
        gdb.execute('set pagination off');gdb.execute('set confirm off');gdb.execute('set disable-randomization off')
        gdb.execute('file '+config['fixture']);gdb.execute('break *'+hex(NOP_PC));gdb.execute('run');started=True
        out['fixture_sha256']=hashlib.sha256(Path(config['fixture']).read_bytes()).hexdigest()
        control,witness=cap.observe_control();frame=gdb.newest_frame();proof={}
        out.update(architecture=frame.architecture().name(),control_witness=witness,
            state=cap.collect_state(frame,control,raw_evidence=proof),raw_evidence=proof,fields=fields(frame),
            fxsave_hex=bytes(gdb.selected_inferior().read_memory(BASE+0xe00,512)).hex(),
            input_fxrestore_hex=bytes(gdb.selected_inferior().read_memory(BASE+0x1000,512)).hex())
        if config['mode']=='full':
            stimuli={}
            for i in range(32):
                name='zmm'+str(i);v=frame.read_register(name);bits=bytes((i*7+j*13+1)%256 for j in range(64))
                v.assign(gdb.Value(bits,v.type));stimuli[name]=bits.hex()
            for i in range(8):
                name='k'+str(i);v=frame.read_register(name);bits=(0x8000000000000001+i*0x1000100010001).to_bytes(8,'little')
                v.assign(gdb.Value(bits,v.type));stimuli[name]=bits.hex()
            for offset in range(2):
                if int(gdb.newest_frame().read_register('rip'))!=NOP_PC+offset:raise ValueError('exact NOP PC')
                if bytes(gdb.selected_inferior().read_memory(NOP_PC+offset,1))!=b'\x90':raise ValueError('literal NOP byte')
                gdb.execute('stepi')
            receipt={};newframe=gdb.newest_frame()
            out.update(kernel_roundtrip=dict(nop_instructions=2,pc_before=NOP_PC,pc_after=int(newframe.read_register('rip')),
                nop_code_hex='9090',register_cache_invalidated_by_inferior_resume=True),
                seeded_state=cap.collect_state(newframe,control,raw_evidence=receipt),
                seeded_raw_evidence=receipt,seeded_fields=fields(newframe),disposable_register_stimuli=stimuli)
    except Exception as exc:
        out['unknown'].append(str(exc));out['failure_type']=type(exc).__name__
        if hasattr(exc,'diagnostic_receipt'):out['diagnostic_receipt']=exc.diagnostic_receipt
    finally:
        if started:gdb.execute('kill')
        save(config['output'],out)
main()

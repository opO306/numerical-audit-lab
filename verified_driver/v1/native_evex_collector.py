"""Complete finite native row acquisition with truthful actual post state.

Prior-store sampling is recorder observation, never a claimed CPU data read.
Every enabled store is retained even when the byte value is unchanged. Exact
instruction semantics close the architectural footprint; a sampled window alone
does not prove absence of other effects. Checker semantics remain independent.
"""
from copy import deepcopy
from .native_evex_producer import derive_step

PATH=(
    (0x1996c0,'f30f1efa'),(0x1996c4,'62e27d287ac6'),
    (0x1996ca,'4889f8'),(0x1996cd,'4883fa20'),(0x1996d1,'722d'),
    (0x199700,'81e7ff0f0000'),(0x199706,'81ffe00f0000'),
    (0x19970c,'0f87ae000000'),(0x199712,'b9ffffffff'),
    (0x199717,'c4e268f5c9'),(0x19971c,'c5fb92c9'),
    (0x199720,'62e17f297f00'),(0x199726,'c3'))


class AcquisitionFailure(ValueError):
    def __init__(self,message,receipt):
        super().__init__(message);self.diagnostic_receipt=receipt


def _record_step(elf_pc,code,before,read_memory,execute_step,collect_after,load_base,diagnostic):
    frozen=deepcopy(before)
    diagnostic.update(stage='derive-input',before=frozen)
    expected=derive_step(elf_pc,code,frozen,read_memory,load_base)
    samples=[]
    diagnostic.update(stage='read-pre-store',reads=expected['reads'],attempted_writes=samples)
    for write in expected['writes']:
        raw=read_memory(write['address'],write['size'])
        if type(raw) is not bytes or len(raw)!=write['size']:
            raise ValueError('complete pre-store bytes unavailable')
        samples.append(dict(write,before_hex=raw.hex()))
    diagnostic['stage']='execute-instruction'
    execute_step()
    diagnostic['stage']='collect-post-state'
    actual=deepcopy(collect_after())
    diagnostic.update(stage='compare-post-state',after=actual)
    compared=deepcopy(actual)
    mask=expected['defined_flags_mask']
    # Keep actual undefined AF/PF in the evidence. Only comparison masks them.
    compared['registers']['eflags']=(compared['registers']['eflags']&mask)
    predicted=deepcopy(expected['after'])
    predicted['registers']['eflags']&=mask
    if compared!=predicted:
        diagnostic['stage']='compare-post-state'
        raise AcquisitionFailure('actual native state differs from producer derivation',diagnostic)
    for sample in samples:
        diagnostic['stage']='read-post-store'
        raw=read_memory(sample['address'],sample['size'])
        sample['actual_after_hex']=raw.hex() if type(raw) is bytes else None
        if type(raw) is not bytes or raw.hex()!=sample['after_hex']:
            diagnostic.update(stage='compare-memory',attempted_writes=deepcopy(samples))
            raise AcquisitionFailure('actual store differs from producer derivation',diagnostic)
        sample['value_changed']=sample['before_hex']!=sample['after_hex']
        sample['basis']='DERIVED_ENABLED_STORE_WITH_ACTUAL_PRE_POST_BYTES'
    return dict(elf_pc=elf_pc,instruction_bytes=code,before=frozen,after=actual,
        reads=expected['reads'],writes=expected['writes'],write_observations=samples,
        defined_flags_mask=mask)


def record_step(elf_pc,code,before,read_memory,execute_step,collect_after,load_base):
    diagnostic=dict(elf_pc=elf_pc,instruction_bytes=code,before=deepcopy(before),after=None,
        stage='startup',reads=[],attempted_writes=[],measurement_accepted=False)
    try:
        return _record_step(elf_pc,code,before,read_memory,execute_step,collect_after,load_base,diagnostic)
    except AcquisitionFailure:
        raise
    except Exception as exc:
        if getattr(exc,'diagnostic_receipt',None) is not None:
            diagnostic['acquisition_diagnostic']=deepcopy(exc.diagnostic_receipt)
        diagnostic.update(exception_type=type(exc).__name__,exception_message=str(exc))
        raise AcquisitionFailure(str(exc),deepcopy(diagnostic)) from exc


def project_state(state):
    regs=state['registers']
    names=('rax','rbx','rcx','rdx','rsi','rdi','rbp','rsp',*('r'+str(i) for i in range(8,16)),'rip')
    return dict(gpr={name:f'0x{regs[name]:016x}' for name in names},
        xmm={'xmm'+str(i):'0x'+bytes.fromhex(state['vectors']['zmm'+str(i)])[:16][::-1].hex() for i in range(16)},
        extra_vectors={},segment_bases={name:f'0x{regs[name]:016x}' for name in ('fs_base','gs_base')},
        mxcsr=regs['mxcsr'],eflags=regs['eflags'])


def frame_native(seq,phase,module,mapping,file_offset,assembly,raw,*,owner):
    """Legacy numerical projection plus a single complete native sidecar."""
    index=next((i for i,(pc,code) in enumerate(PATH) if (pc,code)==(raw['elf_pc'],raw['instruction_bytes'])),None)
    if index is None:raise ValueError('unsupported raw native form')
    opcodes=('endbr64','vpbroadcastb','mov','cmp','jb','and','cmp','ja','mov','bzhi','kmovd','vmovdqu8','ret')
    opcode=opcodes[index];kind='CONTROL' if index in (4,7,12) else 'ROUTING'
    operands=[];bits=None
    hx=lambda b:'0x'+bytes(b)[::-1].hex()
    if index==1:
        kind='ZERO_FILL'
        operands=[dict(kind='register',register='esi',width=1,raw_bits=f"0x{raw['before']['registers']['rsi']&255:02x}",access='read'),
            dict(kind='register',register='ymm16',width=32,
                raw_bits=hx(bytes.fromhex(raw['before']['vectors']['zmm16'])[:32]),access='write')]
        bits=hx(bytes.fromhex(raw['after']['vectors']['zmm16'])[:32])
    if index==11:
        kind='MOVE'
        samples=raw['write_observations']
        if len(samples)!=16 or [w['address'] for w in samples]!=list(range(raw['before']['registers']['rax'],raw['before']['registers']['rax']+16)):
            raise ValueError('closed masked zero16 write projection required')
        operands=[dict(kind='register',register='ymm16',width=16,
            raw_bits=hx(bytes.fromhex(raw['before']['vectors']['zmm16'])[:16]),access='read'),
            dict(kind='memory',address=raw['before']['registers']['rax'],width=16,
                raw_bits=hx(b''.join(bytes.fromhex(w['before_hex']) for w in samples)),access='write')]
        bits=hx(b''.join(bytes.fromhex(w['after_hex']) for w in samples))
    if index==12:
        reads=raw['reads']
        if (len(reads)!=1 or reads[0]['address']!=raw['before']['registers']['rsp']
            or type(reads[0]['size']) is not int or reads[0]['size']!=8
            or len(bytes.fromhex(reads[0]['bytes_hex']))!=8):
            raise ValueError('one complete actual RET stack read required')
        operands=[dict(kind='memory',address=reads[0]['address'],width=8,
            raw_bits=hx(bytes.fromhex(reads[0]['bytes_hex'])),access='read')]
    observations=[dict(item,kind='IMPLICIT_RET',operand='(%rsp)',status='OK',timing='PRE_INSTRUCTION') for item in raw['reads']]
    writes=[dict(address=w['address'],size=w['size'],before_hex=w['before_hex'],after_hex=w['after_hex'],
        value_changed=w['before_hex']!=w['after_hex']) for w in raw['write_observations']]
    pre=project_state(raw['before']);post=project_state(raw['after'])
    return dict(seq=seq,pid=owner[0],ptid=list(owner),phase=phase,occurrence=phase,step=0 if phase=='init' else 1,
        module_path=module['path'],module_sha256=module['sha256'],module_load_base=module['load_base'],mapping=mapping,
        elf_file_offset=file_offset,runtime_pc=raw['before']['registers']['rip'],
        elf_address=raw['elf_pc'],bytes=raw['instruction_bytes'],instruction=assembly,opcode=opcode,kind=kind,
        operands=operands,result_bits=bits,pre=pre,post=post,post_pc=raw['after']['registers']['rip'],
        changed_gpr_results={name:value for name,value in post['gpr'].items() if name!='rip' and value!=pre['gpr'][name]},
        pre_memory_observations=observations,possible_memory_writes=writes,
        native_evex={k:deepcopy(raw[k]) for k in ('before','after','reads','writes')})


LIBC_SHA='3a15d66867d83762c7f2f1e37359cb8f6c5743edb369c65285cb0b1c4f7498bf'
GALA_SHA='a6ac98736304bb9f6a92e473bba45da10d9b5b99f8019e2ca15eb6a7f86234fc'
PROFILE_ID='libc-memset-avx512-evex-16zero-v1'
CALLERS={0x35689:'e8c20cfdff',0x6350:'ff253aae0300'}


class _SidecarStream:
    """Add full caller truth before the reviewed stream's global chain hash.

    Its raw property deliberately preserves the existing bounded-stream/file
    chain: capture.stream.raw.raw is still the quota-reserved underlying file.
    """
    def __init__(self,capture,stream):self.capture,self.stream=capture,stream
    @property
    def raw(self):return self.stream.raw
    @property
    def closed(self):return self.stream.closed
    def close(self):return self.stream.close()
    def flush(self):return self.stream.flush()
    def write(self,text):
        if self.capture._pending_caller is not None or self.capture._native_state_acquisitions:
            import json
            row=json.loads(text)
            if self.capture._pending_caller is not None:
                row['native_evex_caller']=self.capture._caller_after(row)
            row['native_evex_state_acquisitions']=deepcopy(self.capture._native_state_acquisitions)
            text=json.dumps(row,separators=(',',':'))+'\n'
            count=self.stream.write(text)
            self.capture._native_state_acquisitions.clear()
            return count
        return self.stream.write(text)


def make_capture(Parent,gdb,profile_binding):
    """Return an opt-in Capture subclass after caller-side registry admission.

    The three fields identify the already admitted profile and actual V1 source
    snapshot; they cannot themselves issue authority. Parent construction keeps
    the reviewed 512 MiB writer reservation. No Runtime source is modified.
    """
    import json
    from pathlib import Path
    import re
    from . import native_evex_capture as acquisition
    if (type(profile_binding) is not dict or set(profile_binding)!={
            'profile_id','manifest_sha256','source_binding'}
        or profile_binding['profile_id']!=PROFILE_ID
        or any(type(profile_binding[k]) is not str or
               re.fullmatch('[0-9a-f]{64}',profile_binding[k]) is None
               for k in ('manifest_sha256','source_binding'))):
        raise ValueError('explicit finite source-bound native profile identity required')
    frozen_binding=deepcopy(profile_binding)

    class NativeCapture(Parent):
        def __init__(self):
            super().__init__()  # Includes the existing quota reservation.
            self.stream=_SidecarStream(self,self.stream)
            self.native_profile_binding=deepcopy(frozen_binding)
            self.native_spans=[];self._active_native=None;self._caller_stage=None
            self._pending_caller=None;self._current_diagnostic=None
            self._acquired_memory=[]
            self._native_state_acquisitions=[]
            try:
                self._native_control,self.native_evex_control_witness=acquisition.observe_control()
                if acquisition.control_from_witness(self.native_evex_control_witness)!=self._native_control:
                    raise ValueError('actual CPUID witness/control mismatch')
            except Exception as exc:
                self._save_failure(exc,dict(seq=self.count,stage='observe-control',before=None,
                    after=None,measurement_accepted=False))

        def context(self,extras=()):
            result=super().context(extras)
            if result.get('extra_vectors',{}):
                raise ValueError('legacy vector extras outside admitted scalar path')
            result['extra_vectors']={}
            return result

        def _full_state(self):
            if len(self._native_state_acquisitions)>=64:
                raise ValueError('bounded native state acquisition evidence limit')
            evidence={}
            state=acquisition.collect_state(gdb.newest_frame(),self._native_control,raw_evidence=evidence)
            self._native_state_acquisitions.append(dict(sample_index=len(self._native_state_acquisitions),
                trace_sequence=self.count,context_rip=state['registers']['rip'],
                evidence=deepcopy(evidence)))
            return state

        def _read(self,address,size):
            return bytes(gdb.selected_inferior().read_memory(address,size))

        def _owner_check(self):
            if (gdb.selected_thread().ptid!=self.owner or
                gdb.selected_inferior().pid!=self.process_identity['pid']):
                raise ValueError('native process/thread identity drift')

        def _step(self):
            self.last_event=None
            gdb.execute('stepi',to_string=True)
            if isinstance(self.last_event,gdb.SignalEvent):
                raise ValueError('signal during native stepi: '+self.last_event.stop_signal)
            self._owner_check()

        def _save_failure(self,exc,receipt=None):
            combined=deepcopy(self._current_diagnostic or {})
            combined.update(deepcopy(receipt or {}))
            combined.update(deepcopy(getattr(exc,'diagnostic_receipt',None) or {}))
            receipt=combined
            receipt.update(seq=self.count,measurement_accepted=False,exception_type=type(exc).__name__,
                exception_message=str(exc),active_span=deepcopy(self._active_native),
                acquired_memory=deepcopy(self._acquired_memory),
                native_evex_state_acquisitions=deepcopy(self._native_state_acquisitions))
            try:self.stream.flush()
            except Exception as error:receipt['trace_flush_error']=str(error)
            try:
                data=(json.dumps(receipt,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
                if len(data)>1048576:raise ValueError('native diagnostic 1 MiB ceiling')
                output=Path(self.stream.raw.raw.name).parent
                from runtime_trace.regular_nstep.acquire import write
                write(output/'native-diagnostic.json',receipt)
            except Exception as error:
                receipt['diagnostic_write_error']=str(error)
            raise AcquisitionFailure(str(exc),receipt) from exc

        @staticmethod
        def _canonical_address(address,size=1):
            if (type(address) is not int or not 0<=address<1<<64 or address+size>1<<64 or
                not (address<1<<47 or address>=((1<<64)-(1<<47))) or
                not (address+size-1<1<<47 or address+size-1>=((1<<64)-(1<<47)))):
                raise ValueError('finite canonical48 address required')
            return address

        def _site(self,before):
            pc=before['registers']['rip'];module,mapping=self.module_at(pc)
            ins=gdb.newest_frame().architecture().disassemble(pc,count=1)[0]
            length=ins.get('length')
            if type(length) is not int or not 1<=length<=15:
                raise ValueError('complete GDB instruction length required')
            code=self._read(pc,length);disk,offset=self.file_slice(module,pc,length)
            if code!=disk or len(code)!=length:
                raise ValueError('actual code differs from pinned ELF bytes')
            return module,mapping,pc-module['load_base'],code.hex(),offset,ins['asm']

        def _caller_input(self,pc,code,before,module,phase):
            if code!=CALLERS[pc]:raise ValueError('pinned actual Gala CALL/PLT bytes required')
            regs=before['registers'];after=deepcopy(before);reads=[];writes=[]
            pending=dict(kind='CALL' if pc==0x35689 else 'PLT',before=deepcopy(before),expected=after,
                reads=reads,writes=writes,phase=phase,pre_stack_hex=None,write_observations=[])
            self._current_diagnostic['caller_acquisition']=pending
            memory=dict(seq=self.count,kind=pending['kind'],elf_pc=pc,reads=reads,
                        write_observations=pending['write_observations'])
            self._acquired_memory.append(memory)
            if pc==0x35689:
                if self._caller_stage is not None:raise ValueError('duplicate or interrupted native caller')
                address=self._canonical_address(regs['rsp']-8,8)
                target=self._canonical_address(regs['rip']+5+int.from_bytes(bytes.fromhex(code)[1:],'little',signed=True))
                if target!=module['load_base']+0x6350:raise ValueError('exact CALL-to-PLT target required')
                value=(regs['rip']+5).to_bytes(8,'little').hex()
                writes.append(dict(address=address,size=8,after_hex=value))
                after['registers'].update(rip=target,rsp=address)
                sample=self._read(address,8)
                pending['pre_stack_hex']=sample.hex()
                pending['write_observations'].append(dict(writes[0],before_hex=sample.hex()))
                if len(sample)!=8:raise ValueError('complete actual CALL stack pre-read required')
            else:
                if self._caller_stage is None or self._caller_stage['kind']!='CALL':
                    raise ValueError('PLT requires the actual preceding CALL row')
                if before!=self._caller_stage['after'] or phase!=self._caller_stage['phase']:
                    raise ValueError('complete CALL/PLT context seam required')
                address=self._canonical_address(regs['rip']+6+int.from_bytes(bytes.fromhex(code)[2:],'little',signed=True),8)
                raw=self._read(address,8)
                reads.append(dict(address=address,size=8,bytes_hex=raw.hex()))
                if len(raw)!=8:raise ValueError('complete actual PLT GOT read required')
                target=self._canonical_address(int.from_bytes(raw,'little'))
                resolved,_=self.module_at(target)
                if resolved['sha256']!=LIBC_SHA or target-resolved['load_base']!=PATH[0][0]:
                    raise ValueError('actual GOT must resolve exact admitted libc entry')
                after['registers']['rip']=target
            return pending

        def _caller_after(self,row):
            pending=self._pending_caller;actual=self._full_state()
            self._current_diagnostic.update(stage='compare-caller-state',after=deepcopy(actual))
            pending['after']=deepcopy(actual)
            self._owner_check()
            if isinstance(self.last_event,gdb.SignalEvent):raise ValueError('signal during caller stepi')
            for sample in pending['write_observations']:
                raw=self._read(sample['address'],sample['size'])
                sample['actual_after_hex']=raw.hex()
                if len(raw)==sample['size']:
                    sample['value_changed']=sample['before_hex']!=raw.hex()
                    sample['basis']='DERIVED_ENABLED_STORE_WITH_ACTUAL_PRE_POST_BYTES'
            if actual!=pending['expected']:raise ValueError('actual full caller state differs from exact CALL/PLT')
            if row['pre']!=project_state(pending['before']) or row['post']!=project_state(actual):
                raise ValueError('legacy/full caller state projection mismatch')
            extras=self.row_extras
            observed=extras['pre_memory_observations']
            if [dict(address=r['address'],size=r['size'],bytes_hex=r['bytes_hex']) for r in observed]!=pending['reads']:
                raise ValueError('legacy/full caller read mismatch')
            writes=extras['possible_memory_writes']
            if [(w['address'],w['size']) for w in writes]!=[(w['address'],w['size']) for w in pending['writes']]:
                raise ValueError('legacy/full caller write mismatch')
            for write,descriptor,sample in zip(writes,pending['writes'],pending['write_observations']):
                if write['before_hex']!=pending['pre_stack_hex'] or sample['actual_after_hex']!=descriptor['after_hex']:
                    raise ValueError('actual CALL stack pre/post bytes mismatch')
            sidecar=dict(before=deepcopy(pending['before']),after=actual,
                         reads=deepcopy(pending['reads']),writes=deepcopy(pending['writes']))
            self._caller_stage=dict(kind=pending['kind'],after=deepcopy(actual),phase=pending['phase'],
                                   return_pc=pending['before']['registers']['rip']+5 if pending['kind']=='CALL' else self._caller_stage['return_pc'])
            return sidecar

        def _native_one(self,phase,before,module,mapping,pc,code,offset,assembly):
            if self._active_native is None:
                if (pc!=PATH[0][0] or self._caller_stage is None or self._caller_stage['kind']!='PLT'
                    or before!=self._caller_stage['after'] or phase!=self._caller_stage['phase']):
                    raise ValueError('native entry requires actual complete CALL/PLT prefix')
                if before['registers']['rdx']!=16 or before['registers']['rsi']&255:
                    raise ValueError('only admitted exact16 zero-fill acquisition supported')
                self._active_native=dict(start_seq=self.count,index=0,phase=phase,previous=deepcopy(before),
                    return_pc=self._caller_stage['return_pc'])
            active=self._active_native;index=active['index']
            if (module['sha256']!=LIBC_SHA or (pc,code)!=PATH[index] or phase!=active['phase']
                or before!=active['previous']):raise ValueError('active native exact PC/code/context path interrupted')
            self.pending=deepcopy(self._current_diagnostic)
            raw=record_step(pc,code,before,self._read,self._step,self._full_state,module['load_base'])
            self._current_diagnostic.update(stage='frame-native',after=deepcopy(raw['after']),reads=raw['reads'],
                writes=raw['writes'],completed_native_step=deepcopy(raw))
            self._acquired_memory.append(dict(seq=self.count,kind='NATIVE',elf_pc=pc,
                reads=deepcopy(raw['reads']),write_observations=deepcopy(raw['write_observations'])))
            if index==12 and raw['after']['registers']['rip']!=active['return_pc']:
                raise ValueError('native RET must return to actual Gala CALL successor')
            row=frame_native(self.count,phase,module,mapping,offset,assembly,raw,owner=self.owner)
            row['symbol']=gdb.newest_frame().name() or 'memset'
            for operand in row['operands']:
                data=int(operand['raw_bits'],16).to_bytes(operand['width'],'little')
                operand['origins']=self.origins(operand,data)
            self.forget_changed_gprs(row['pre'],row['post'],{'rsp'} if index==12 else ())
            if index in (1,11):
                destination=row['operands'][-1]
                data=int(row['result_bits'],16).to_bytes(destination['width'],'little')
                if any(data):raise ValueError('finite zero provenance required')
                self.put(destination,data,f'record:{self.count}',False)
            self.row_extras=dict(occurrence=phase,pre_memory_observations=row['pre_memory_observations'],
                                 possible_memory_writes=row['possible_memory_writes'])
            try:
                self.stream.write(json.dumps(row,separators=(',',':'))+'\n');self.stream.flush()
            finally:self.row_extras=None
            self.pre_memory_observation_count+=len(row['pre_memory_observations'])
            self.possible_memory_write_count+=len(row['possible_memory_writes'])
            self.count+=1;opcode=row['opcode'];self.histogram[opcode]=self.histogram.get(opcode,0)+1
            active.update(index=index+1,previous=deepcopy(raw['after']))
            if index==12:
                self.native_spans.append(dict(start_seq=active['start_seq'],end_seq=self.count))
                self._active_native=None;self._caller_stage=None
            self.pending=None

        def one(self,phase):
            self._current_diagnostic=dict(seq=self.count,stage='collect-current-state',before=None,after=None,
                                          measurement_accepted=False)
            try:
                # Full capture is required at the finite native/caller sites.
                # Ordinary scalar rows retain the reviewed parent's collection.
                self._owner_check()
                runtime_pc=int(gdb.newest_frame().read_register('rip'))
                module,_=self.module_at(runtime_pc);pc=runtime_pc-module['load_base']
                native=module['sha256']==LIBC_SHA and pc in {p for p,_ in PATH}
                caller=module['sha256']==GALA_SHA and pc in CALLERS
                if not native and not caller and self._active_native is None and self._caller_stage is None:
                    return super().one(phase)
                before=self._full_state();self._current_diagnostic.update(before=deepcopy(before),runtime_pc=runtime_pc,elf_pc=pc)
                module,mapping,pc,code,offset,assembly=self._site(before)
                self._current_diagnostic.update(instruction_bytes=code,module_sha256=module['sha256'],stage='validate-current-site')
                if self._active_native is not None or native:
                    return self._native_one(phase,before,module,mapping,pc,code,offset,assembly)
                if caller:
                    self._pending_caller=self._caller_input(pc,code,before,module,phase)
                    try:return super().one(phase)
                    finally:self._pending_caller=None
                raise ValueError('actual native CALL/PLT path escaped before entry')
            except Exception as exc:
                self._save_failure(exc)
            finally:self._current_diagnostic=None

    return NativeCapture

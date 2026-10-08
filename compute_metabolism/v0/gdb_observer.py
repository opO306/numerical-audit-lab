"""GDB-only collector for one bounded synthetic pinned-libc memset call.

Machine observations are retained without borrowing producer/checker semantics.
Decoded operand effects carry an explicit observer-only basis. Every row keeps
UNKNOWN for complete effects and is ineligible for automatic promotion.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

import gdb

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from compute_metabolism.v0.adaptive import canonical, elf_build_id


GPRS = ('rax','rbx','rcx','rdx','rsi','rdi','rbp','rsp','r8','r9','r10','r11','r12','r13','r14','r15','rip','eflags')


def registers():
    frame = gdb.newest_frame()
    result = dict(registers={},vectors={},unavailable=[])
    for name in GPRS:
        result['registers'][name] = int(frame.read_register(name))
    for index in range(32):
        # AVX2 machines expose YMM but no ZMM. Read the widest available view;
        # absent views remain explicitly unavailable rather than zero-filled.
        for prefix,size in (('zmm',64),('ymm',32),('xmm',16)):
            name = prefix+str(index)
            try:
                reg = frame.read_register(name)['v'+str(size)+'_int8']
                result['vectors'][name] = bytes(int(reg[i]) & 255 for i in range(size)).hex()
                break
            except (gdb.error,ValueError,TypeError):
                result['unavailable'].append(name)
    for name in ('mxcsr','fs_base','gs_base'):
        try:
            result['registers'][name] = int(frame.read_register(name))
        except (gdb.error,ValueError):
            result['unavailable'].append(name)
    result['unavailable'].append('X87_RAW_BITS_AND_SYSTEM_STATE_NOT_SAMPLED')
    for index in range(8):
        name = 'k'+str(index)
        try:
            result['registers'][name] = int(frame.read_register(name))
        except (gdb.error,ValueError):
            result['unavailable'].append(name)
    return result


def mapping(address,pid):
    maps = Path('/proc/'+str(pid)+'/maps').read_text().splitlines()
    entries = []
    for line in maps:
        fields = line.split(maxsplit=5)
        if len(fields) < 6 or not fields[5].startswith('/'):
            continue
        start,end = (int(v,16) for v in fields[0].split('-'))
        entries.append(dict(start=start,end=end,offset=int(fields[2],16),
            permissions=fields[1],path=fields[5]))
    hits = [item for item in entries if item['start'] <= address < item['end']]
    if len(hits) != 1:
        raise ValueError('unique file-backed instruction mapping required')
    item = hits[0]
    path = Path(item['path']).resolve(strict=True)
    raw = path.read_bytes()
    if len(raw) > 32*1024*1024:
        raise ValueError('bounded mapped ELF required')
    return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),build_id=elf_build_id(raw),
        load_base=item['start']-item['offset'],segments=[v for v in entries if v['path']==item['path']])


def memory(address,size):
    if type(size) is not int or not 0 <= size <= 8192:
        raise ValueError('bounded memory observation required')
    return bytes(gdb.selected_inferior().read_memory(address,size))


def address_of(expression,regs):
    """Parse only Intel base/index/scale/constant syntax; never eval code."""
    expression = expression.strip().replace(' ','')
    if not expression or not re.fullmatch(r'[a-z0-9x+*\-]+',expression):
        raise ValueError('unknown memory address expression')
    total = 0
    tokens = re.findall(r'[+-]?[^+-]+',expression)
    if ''.join(tokens) != expression:
        raise ValueError('unparsed memory address')
    for token in tokens:
        sign = -1 if token.startswith('-') else 1
        token = token.lstrip('+-')
        factors = token.split('*')
        if len(factors)>2:
            raise ValueError('unknown address product')
        value = 1
        for factor in factors:
            if factor in regs:
                value *= regs[factor]
            elif re.fullmatch(r'(?:0x[0-9a-f]+|[0-9]+)',factor):
                value *= int(factor,0)
            else:
                raise ValueError('unknown address register')
        total += sign*value
    return total & ((1<<64)-1)


def explicit_effect(assembly,before,length):
    """Restricted operand observation, not a trusted instruction-semantics model."""
    text = assembly.lower().split('#',1)[0].strip()
    if text == 'ret':
        return dict(address=before['registers']['rsp'],size=8,direction='READ',
            basis='RESTRICTED_OBSERVER_RETURN_OPERAND_DECODE')
    match = re.search(r'\b(zmmword|ymmword|xmmword|qword|dword|word|byte) ptr \[([^\]]+)\]',text)
    if not match:
        return None
    op = text.split()[0]
    if op not in ('mov','movabs','movups','movaps','movdqu','movdqa','vmovups','vmovaps',
        'vmovdqu','vmovdqa','vmovdqu8','vmovdqu16','vmovdqu32','vmovdqu64',
        'vmovdqa32','vmovdqa64','cmp','test'):
        return None
    if '{' in text or 'gs:' in text or 'fs:' in text:
        return None
    width = dict(byte=1,word=2,dword=4,qword=8,xmmword=16,ymmword=32,zmmword=64)[match[1]]
    operands = text[len(op):].strip().split(',')
    if len(operands) != 2:
        return None
    write = '[' in operands[0] and op not in ('cmp','test')
    regs = dict(before['registers'])
    # RIP-relative memory is based on the end of this instruction.
    regs['rip'] += length
    return dict(address=address_of(match[2],regs),size=width,
        direction='WRITE' if write else 'READ',basis='RESTRICTED_OBSERVER_OPERAND_DECODE')


def changes(before,after,address):
    result = []
    index = 0
    while index < len(before):
        if before[index] == after[index]:
            index += 1
            continue
        end = index+1
        while end < len(before) and before[end] != after[end]:
            end += 1
        result.append(dict(address=address+index,size=end-index,before_hex=before[index:end].hex(),
            after_hex=after[index:end].hex(),basis='OBSERVED_CHANGED_BYTES_ONLY'))
        index = end
    return result


def run(config,result):
    started = time.monotonic()
    for command in ('set pagination off','set confirm off','set print thread-events off',
        'set disassembly-flavor intel','handle SIGSTOP stop nopass',
        'set disable-randomization off'):
        gdb.execute(command,to_string=True)
    gdb.execute('run',to_string=True)
    marker = json.loads(Path(config['marker']).read_bytes())
    pid = gdb.selected_inferior().pid
    if pid != marker['pid']:
        raise ValueError('inferior marker PID mismatch')
    lib = mapping(marker['entry'],pid)
    fp = config['fingerprint']
    if (lib['sha256'] != fp['libc']['sha256'] or lib['build_id'] != fp['libc']['build_id']):
        raise ValueError('actual resolved IFUNC library differs from pinned libc')
    # Current stop is in libc kill. Verify /proc/exe separately.
    exe = Path('/proc/'+str(pid)+'/exe').resolve(strict=True)
    if hashlib.sha256(exe.read_bytes()).hexdigest() != fp['runtime']['sha256']:
        raise ValueError('inferior executable differs from pinned Python')
    result['library'] = lib
    result['entry'] = marker['entry']-lib['load_base']
    result['resolved_entry_symbol'] = gdb.execute('info symbol '+str(marker['entry']),to_string=True).strip()
    result['input'].update(destination=marker['destination'],window_address=marker['window_address'],
        window_size=marker['window_size'],initial_window_hex=memory(marker['window_address'],marker['window_size']).hex())
    breakpoint = gdb.Breakpoint('*'+hex(marker['entry']),internal=True)
    breakpoint.condition = ('$rdi == '+str(marker['destination'])+' && $rsi == '+str(config['value'])+
        ' && $rdx == '+str(config['length']))
    gdb.execute('continue',to_string=True)
    breakpoint.enabled = False
    if int(gdb.parse_and_eval('$pc')) != marker['entry']:
        raise ValueError('actual inferior did not reach resolved memset entry')
    return_pc = int.from_bytes(memory(int(gdb.parse_and_eval('$rsp')),8),'little')
    caller = mapping(return_pc,pid)
    caller.update(return_pc=return_pc,return_elf_pc=return_pc-caller['load_base'])
    result['call_origin']['native_caller'] = caller
    result['call_origin']['call_instruction'] = 'UNKNOWN_RETURN_ADDRESS_IDENTIFIED_ONLY'
    initial = memory(marker['window_address'],marker['window_size'])
    result['start_state'] = registers()
    cumulative = len(canonical(result))+16384
    for seq in range(config['max_steps']):
        if time.monotonic()-started > config['timeout_seconds']:
            result['terminal']['status'] = 'STOP_TIMEOUT'
            break
        before = registers()
        pc = before['registers']['rip']
        segment = next((s for s in lib['segments'] if s['start'] <= pc < s['end']),None)
        if segment is None or 'x' not in segment['permissions']:
            result['terminal']['status'] = 'STOP_PATH_ESCAPE'
            break
        insn = gdb.newest_frame().architecture().disassemble(pc,count=1)[0]
        raw = memory(pc,insn['length']).hex()
        window_before = memory(marker['window_address'],marker['window_size'])
        row = dict(seq=seq,pc=pc-lib['load_base'],absolute_pc=pc,bytes=raw,instruction_bytes=raw,
            assembly=insn['asm'],before=before,after=None,reads=[],writes=[],
            memory_effects_complete=False,unknown_effects=['COMPLETE_ARCHITECTURAL_AND_MEMORY_EFFECTS_UNPROVED'])
        effect = None
        try:
            effect = explicit_effect(insn['asm'],before,insn['length'])
            if effect:
                effect['before_hex'] = memory(effect['address'],effect['size']).hex()
        except (ValueError,gdb.error):
            row['unknown_effects'].append('EXPLICIT_OPERAND_ADDRESS_OR_BYTES_UNAVAILABLE')
            effect = None
        gdb.execute('stepi',to_string=True)
        row['after'] = registers()
        row['next_pc'] = row['after']['registers']['rip']-lib['load_base']
        row['absolute_next_pc'] = row['after']['registers']['rip']
        window_after = memory(marker['window_address'],marker['window_size'])
        row['window_changes'] = changes(window_before,window_after,marker['window_address'])
        if effect:
            effect['after_hex'] = memory(effect['address'],effect['size']).hex()
            if effect.pop('direction') == 'READ':
                effect['bytes_hex'] = effect['before_hex']
                row['reads'].append(effect)
            else:
                row['writes'].append(effect)
        else:
            row['writes'].extend(row['window_changes'])
            row['unknown_effects'].append('READS_AND_SAME_VALUE_WRITES_UNRESOLVED')
        row['changed_registers'] = [key for key,value in before['registers'].items()
            if row['after']['registers'].get(key)!=value]
        row['changed_vectors'] = [key for key,value in before['vectors'].items()
            if row['after']['vectors'].get(key)!=value]
        cumulative += len(canonical(row))
        if cumulative > config['max_output_bytes']-32768:
            result['terminal']['status'] = 'STOP_OUTPUT_LIMIT'
            break
        result['trace'].append(row)
        if row['absolute_next_pc'] == return_pc:
            final = memory(marker['window_address'],marker['window_size'])
            destination = final[32:32+config['length']]
            result['end_state'] = row['after']
            result['observed_result'] = dict(return_value=row['after']['registers']['rax'],
                destination_hex=destination.hex(),final_window_hex=final.hex(),
                sentinels_unchanged=final[:32]==initial[:32] and final[32+config['length']:]==initial[32+config['length']:],
                destination_matches_requested_value=destination==bytes([config['value']])*config['length'])
            result['effect_coverage'].update(sample_instructions=len(result['trace']),
                sampled_memory_window=dict(address=marker['window_address'],size=marker['window_size']))
            exited = {}
            def on_exit(event):
                exited['code'] = getattr(event,'exit_code',None)
            gdb.events.exited.connect(on_exit)
            try:
                gdb.execute('continue',to_string=True)
            finally:
                gdb.events.exited.disconnect(on_exit)
            result['terminal'].update(status='OBSERVED_RETURN' if exited.get('code')==0 else 'STOP_INFERIOR_EXIT',
                complete=exited.get('code')==0,inferior_exit_code=exited.get('code'),
                scope='ONE_SYNTHETIC_MEMSET_CALL_WITH_UNTRACED_HARNESS_TAIL')
            break
    else:
        result['terminal']['status'] = 'STOP_STEP_LIMIT'


def main():
    config = json.loads(Path(os.environ['CM_OBSERVER_CONFIG']).read_bytes())
    result = config['base']
    try:
        run(config,result)
    except Exception as exc:
        result['terminal'].update(status='STOP_ERROR',complete=False,
            error_type=type(exc).__name__,error=str(exc)[:2048])
    finally:
        if gdb.selected_inferior().pid:
            try:
                gdb.execute('kill',to_string=True)
            except gdb.error:
                result['terminal']['kill_failed'] = True
        with Path(config['result']).open('xb') as stream:
            stream.write(canonical(result))
            stream.flush()
            os.fsync(stream.fileno())


main()

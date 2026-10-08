"""Independent V1 storage graph bridge for the finite authenticated EVEX path.

No producer import or rewritten machine rows. The caller authenticates the
Gala/caller/library domain with native_evex_checker.verify_trace first; this
bridge independently derives every native effect again and binds raw sidecars
to the original projected rows. Scalar/constant/copy/IEEE checks are retained
from the audited regular checker in a V1-owned loop.
"""
from copy import deepcopy
import re

from runtime_trace import correspondence as raw_checker
from runtime_trace.numeric_ir import checker as storage
from runtime_trace.regular_2step import checker as audited
from runtime_trace.semantics import decode, Refused as DecodeRefused
from .native_evex_checker import PATH, U32, derive_step, _context, _typed_equal, _effect_records


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def _raw_bits(data):
    return '0x' + data[::-1].hex()


def _projection(projection, complete):
    _context(complete)
    regs = complete['registers']
    names = {'rax', 'rbx', 'rcx', 'rdx', 'rsi', 'rdi', 'rbp', 'rsp',
             *(f'r{i}' for i in range(8, 16)), 'rip'}
    require(set(projection['gpr']) == names, 'native projected GPR keys')
    for name in names:
        require(projection['gpr'][name] == f"0x{regs[name]:016x}", 'native projected GPR bits')
    require(set(projection['xmm']) == {f'xmm{i}' for i in range(16)}, 'native projected XMM keys')
    for i in range(16):
        require(projection['xmm'][f'xmm{i}'] == _raw_bits(bytes.fromhex(complete['vectors'][f'zmm{i}'])[:16]),
                'native projected XMM bits')
    require(type(projection['eflags']) is int and projection['eflags'] == regs['eflags'] and
            type(projection['mxcsr']) is int and projection['mxcsr'] == regs['mxcsr'], 'native projected control bits')
    require(projection['segment_bases'] == {name: f"0x{regs[name]:016x}" for name in ('fs_base', 'gs_base')},
            'native projected segment bases')
    for name, value in projection.get('extra_vectors', {}).items():
        match = re.fullmatch(r'(xmm|ymm|zmm)(\d+)', name)
        require(match is not None and int(match[2]) < 32, 'native extra vector name')
        width = {'xmm': 16, 'ymm': 32, 'zmm': 64}[match[1]]
        require(value == _raw_bits(bytes.fromhex(complete['vectors'][f'zmm{match[2]}'])[:width]),
                'native extra vector bits')


def _raw_effects(row, sidecar):
    _effect_records(sidecar['reads'], False)
    _effect_records(sidecar['writes'], True)
    reads = row.get('pre_memory_observations', [])
    require(type(reads) is list, 'native raw reads list')
    normalized = []
    for record in reads:
        require(record.get('status', 'OK') == 'OK' and record.get('timing', 'PRE_INSTRUCTION') == 'PRE_INSTRUCTION',
                'native unreadable/nonpre read')
        normalized.append({k: record[k] for k in ('address', 'size', 'bytes_hex')})
    require(_typed_equal(normalized, sidecar['reads']), 'native raw CPU reads bind sidecar')
    writes = row.get('possible_memory_writes', [])
    require(type(writes) is list and len(writes) == len(sidecar['writes']), 'native raw activated write count')
    for record, expected in zip(writes, sidecar['writes']):
        after, before = record.get('after_hex'), record.get('before_hex')
        if after is None and 'after_bits' in record:
            after = raw_checker.raw(record['after_bits'], record['size']).hex()
        if before is None and 'before_bits' in record:
            before = raw_checker.raw(record['before_bits'], record['size']).hex()
        require(_typed_equal({k: record[k] for k in ('address', 'size')}, {k: expected[k] for k in ('address', 'size')}) and
                after == expected['after_hex'], 'native raw writes bind exact sidecar')
        require(type(before) is str and re.fullmatch('[0-9a-f]{2}', before) is not None,
                'native raw write pre-byte')
        require(type(record.get('value_changed')) is bool and record['value_changed'] == (before != after),
                'native raw same-value write evidence')


def _native_spans(rows, regions, verified_spans):
    require(type(verified_spans) is list, 'verified spans list')
    covered, active = set(), {}
    selected = {i for region in regions for i in range(region['start_seq'], region['end_seq'])}
    for span in verified_spans:
        require(type(span) is dict and set(span) == {'start_seq', 'end_seq'}, 'verified span exact keys')
        start, end = span['start_seq'], span['end_seq']
        require(type(start) is int and type(end) is int and 0 <= start < end and end - start == 13,
                'verified span thirteen dense rows')
        ids = set(range(start, end))
        require(not ids & covered, 'overlapping verified spans')
        covered |= ids
        if not ids & selected:
            continue
        require(ids <= selected and any(region['start_seq'] <= start and end <= region['end_seq'] for region in regions),
                'native span crosses selected region')
        require(end <= len(rows), 'native span missing raw rows')
        block = rows[start:end]
        owner, module, base = block[0]['ptid'], block[0]['module_sha256'], block[0]['module_load_base']
        shadow = None
        for index, (row, (pc, code)) in enumerate(zip(block, PATH)):
            require(row['seq'] == start + index and row['elf_address'] == pc and row['bytes'] == code,
                    'native span exact dense byte path')
            require(row['ptid'] == owner and row['module_sha256'] == module and row['module_load_base'] == base,
                    'native span owner/library continuity')
            sidecar = row.get('native_evex')
            require(type(sidecar) is dict and set(sidecar) == {'before', 'after', 'reads', 'writes'}, 'native full sidecar required')
            _context(sidecar['before'])
            _context(sidecar['after'])
            if shadow is None:
                shadow = deepcopy(sidecar['before'])
                require(shadow['registers']['rdx'] == 16 and shadow['registers']['rsi'] & 255 == 0 and
                        shadow['registers']['rdi'] & 0xFFF <= 0xFE0, 'native sixteen zero bytes route')
            require(sidecar['before'] == shadow, 'native full shadow continuity')
            _projection(row['pre'], sidecar['before'])
            _projection(row['post'], sidecar['after'])
            require(row['runtime_pc'] == base + pc and row['post_pc'] == sidecar['after']['registers']['rip'],
                    'native actual PC projection')
            cursor = 0

            def read(address, size):
                nonlocal cursor
                require(cursor < len(sidecar['reads']), 'native omitted RET read')
                record = sidecar['reads'][cursor]
                require(record['address'] == address and record['size'] == size, 'native RET read range')
                cursor += 1
                return bytes.fromhex(record['bytes_hex'])

            derived = derive_step(pc, code, shadow, read, base)
            require(cursor == len(sidecar['reads']) and _typed_equal(derived['reads'], sidecar['reads']) and
                    _typed_equal(derived['writes'], sidecar['writes']), 'native complete activated effects')
            unknown = U32 ^ derived['defined_flags_mask']
            derived['after']['registers']['eflags'] = ((derived['after']['registers']['eflags'] & ~unknown) |
                                                    (sidecar['after']['registers']['eflags'] & unknown))
            require(derived['after'] == sidecar['after'], 'native independently derived full post')
            _raw_effects(row, sidecar)
            active[row['seq']] = sidecar
            shadow = derived['after']
    marked = {i for i in selected if rows[i].get('native_evex') is not None}
    require(marked == set(active), 'native sidecars must exactly cover verified spans')
    return active


def _native_numeric(row, sidecar):
    pc = row['elf_address']
    if pc == 0x1996C4:
        require(row['opcode'] == 'vpbroadcastb' and row['kind'] == 'ZERO_FILL' and len(row['operands']) == 2,
                'native broadcast recorded form')
        src, dst = row['operands']
        require(src['kind'] == 'register' and src['register'] == 'esi' and src['width'] == 1 and
                src['access'] == 'read' and src['raw_bits'] == '0x00', 'native broadcast source projection')
        require(dst['kind'] == 'register' and dst['register'] == 'ymm16' and dst['width'] == 32 and
                dst['access'] == 'write', 'native broadcast destination projection')
        require(row['result_bits'] == '0x' + '00' * 32 and dst['raw_bits'] ==
                _raw_bits(bytes.fromhex(sidecar['before']['vectors']['zmm16'])[:32]), 'native broadcast raw bits')
    elif pc == 0x199720:
        require(row['opcode'] == 'vmovdqu8' and row['kind'] == 'MOVE' and len(row['operands']) == 2,
                'native masked store recorded form')
        src, dst = row['operands']
        require(sidecar['before']['registers']['k1'] == 0xFFFF, 'native exact mask contract')
        bits = _raw_bits(bytes.fromhex(sidecar['before']['vectors']['zmm16'])[:16])
        require(src['kind'] == 'register' and src['register'] == 'ymm16' and src['width'] == 16 and
                src['access'] == 'read' and src['raw_bits'] == bits, 'native masked source pre-vector bits')
        require(dst['kind'] == 'memory' and dst['address'] == sidecar['before']['registers']['rax'] and
                dst['width'] == 16 and dst['access'] == 'write' and row['result_bits'] == bits,
                'native masked destination/result contract')
        before_bytes = b''.join(bytes.fromhex(record['before_hex']) if 'before_hex' in record else
                                raw_checker.raw(record['before_bits'], 1) for record in row['possible_memory_writes'])
        require(dst['raw_bits'] == _raw_bits(before_bytes), 'native masked pre-memory operand bits')
    elif pc == 0x199726:
        require(row['opcode'] == 'ret' and row['kind'] == 'CONTROL' and len(row['operands']) == 1, 'native RET recorded form')
        op = row['operands'][0]
        require(op['kind'] == 'memory' and op['address'] == sidecar['reads'][0]['address'] and op['width'] == 8 and
                op['access'] == 'read' and op['raw_bits'] == _raw_bits(bytes.fromhex(sidecar['reads'][0]['bytes_hex'])),
                'native RET operand binding')


def _native_knowledge(record, knowledge, native):
    sidecar = native[record['seq']]
    _native_numeric(record, sidecar)
    for read in sidecar['reads']:
        for offset, byte in enumerate(bytes.fromhex(read['bytes_hex'])):
            key = ('m', read['address'] + offset)
            require(key not in knowledge or knowledge[key] == byte, 'native read carried byte continuity')
    for write, raw_write in zip(sidecar['writes'], record['possible_memory_writes']):
        before_byte = int(raw_write['before_hex'], 16) if 'before_hex' in raw_write else int(raw_write['before_bits'], 16)
        key = ('m', write['address'])
        require(key not in knowledge or knowledge[key] == before_byte, 'native write carried pre-byte continuity')
        knowledge['m', write['address']] = int(write['after_hex'], 16)
    if record['elf_address'] == 0x1996C4:
        for offset in range(64):
            knowledge['r', 'v16', offset] = 0
    for name in record['pre']['gpr']:
        if record['pre']['gpr'][name] != record['post']['gpr'][name]:
            for offset in range(8):
                knowledge.pop(('r', name, offset), None)


# Audited flow rules retained; only native dispatch is added.
def _verify_flow(rows, capture, decoded, root=None, *, native):
    modules=capture["modules"]
    resolver=raw_checker.FrozenBinaryResolver(root)
    for region in capture["regions"]:
        subset=rows[region["start_seq"]:region["end_seq"]]
        knowledge={}
        for name,address in region["pointers"].items():
            for i,byte in enumerate(raw_checker.raw(region["start_state"][name],16)):knowledge["m",address+i]=byte
        for name,index in [("xmm0",0),("xmm1",1)]:
            for i,byte in enumerate(raw_checker.register_raw(subset[0]["pre"],name,8)):knowledge["r",f"v{index}",i]=byte
        for record in subset:
            if record["seq"] in native:
                _native_knowledge(record, knowledge, native)
                continue
            reference=decoded[record["module_path"],record["elf_address"]]
            opcode,args=raw_checker.split_att(reference)
            require(opcode==record["opcode"],"opcode independent decode")
            raw_checker.verify_control_pc(record,reference)
            kind=record["kind"];ops=record["operands"]
            if opcode in {"movslq","movzbl","movzwl"}:
                expected_widths={"movslq":[4,8],"movzbl":[1,4],"movzwl":[2,4]}[opcode]
                require([o["width"] for o in ops]==expected_widths,"integer extension operand widths")
                source=raw_checker.raw(ops[0]["raw_bits"],expected_widths[0])
                expected=int.from_bytes(source,"little",signed=opcode=="movslq")&((1<<(8*expected_widths[1]))-1)
                require(raw_checker.register_raw(record["post"],ops[1]["register"],expected_widths[1])==expected.to_bytes(expected_widths[1],"little"),"integer extension result bits")
            elif opcode in {"cmpb","testb","cmpl","testl","cmpq","testq"}:
                expected_width={"cmpb":1,"testb":1,"cmpl":4,"testl":4,"cmpq":8,"testq":8}[opcode]
                require(all(o["width"]==expected_width for o in ops),"integer memory operand width")
            elif opcode=="vpbroadcastb":
                require(ops[0]["width"]==1 and int(ops[0]["raw_bits"],16)==0,"zero fill source byte")
            for context in [record["pre"],record["post"]]:
                require(context["mxcsr"]&((3<<13)|(1<<15)|(1<<6))==0,"MXCSR control condition")
                require(context["mxcsr"]&0x1f80==0x1f80,"MXCSR exception masks")
            for operand in ops:
                data=raw_checker.raw(operand["raw_bits"],operand["width"])
                if operand["kind"]=="register":
                    require(data==raw_checker.register_raw(record["pre"],operand["register"],operand["width"]),"record operand vs pre raw register")
                if operand["access"] not in {"write","control"}:
                    for key,byte in zip(raw_checker.operand_keys(operand),data):
                        if key in knowledge:require(knowledge[key]==byte,"memory/register def-use bits")
            if kind in {"ADD","SUB","MUL","MOVE"}:
                require(len(args)==2 and len(ops)==2,"two-operand correspondence")
                for text,operand in zip(args,ops):
                    if text.startswith("%"):
                        require(operand["kind"]=="register" and operand["register"]==text[1:],"instruction register operand role")
                    elif not text.startswith("$"):
                        require(operand["kind"]=="memory" and operand["address"]==raw_checker.ea(text,record),"effective address / alias decode")
            if kind=="ROUTING":
                for text,operand in zip(args,ops):
                    if operand["kind"]=="memory":require(operand["address"]==raw_checker.ea(text,record),"routing effective address")
            if kind in {"ADD","SUB","MUL"}:
                require(opcode in {"addsd","subsd","mulsd"},"scalar instruction class")
                for operand in ops:
                    data=raw_checker.raw(operand["raw_bits"],8)
                    keys=raw_checker.operand_keys(operand)
                    if not all(key in knowledge for key in keys):
                        origin=operand.get("constant_origin")
                        require(origin is not None,"unknown numerical input source")
                        image=raw_checker.constant_image(origin,modules,resolver)
                        require(image[origin["file_offset"]:origin["file_offset"]+8]==data,"ELF constant source bytes")
                raw_checker.verify_scalar(record)
            destination=ops[-1] if kind in {"ADD","SUB","MUL","MOVE","STACK","ZERO","ZERO_FILL"} else None
            exempt=set()
            if destination:
                result=raw_checker.raw(record["result_bits"],destination["width"])
                if destination["kind"]=="register":
                    require(result==raw_checker.register_raw(record["post"],destination["register"],destination["width"]),"post destination bits")
                    exempt.add(raw_checker.operand_keys(destination)[0][1])
                if kind in {"MOVE","STACK"}:require(result==raw_checker.raw(ops[0]["raw_bits"],ops[0]["width"]),"copy bit preservation")
                if kind in {"ZERO","ZERO_FILL"}:require(not any(result),"zero source/output")
                src_keys=raw_checker.operand_keys(ops[0]);source_known=[key in knowledge for key in src_keys]
                if ops[0].get("constant_origin"):
                    origin=ops[0]["constant_origin"]
                    image=raw_checker.constant_image(origin,modules,resolver)
                    require(image[origin["file_offset"]:origin["file_offset"]+len(result)]==raw_checker.raw(ops[0]["raw_bits"],len(result)),"constant load bytes")
                    source_known=[True]*len(result)
                for i,(key,byte) in enumerate(zip(raw_checker.operand_keys(destination),result)):
                    if kind not in {"MOVE","STACK"} or i<len(source_known) and source_known[i]:knowledge[key]=byte
                    else:knowledge.pop(key,None)
                if destination["kind"]=="register":
                    name=destination["register"];keyname=raw_checker.operand_keys(destination)[0][1]
                    if name.startswith("xmm"):
                        if opcode in {"movq","vmovd"} or opcode=="movsd" and ops[0]["kind"]=="memory":
                            high=raw_checker.register_raw(record["post"],name,16)[destination["width"]:]
                            require(not any(high),"copy XMM upper zero")
                            for i in range(destination["width"],16):knowledge["r",keyname,i]=0
                        elif opcode=="movsd":
                            require(raw_checker.register_raw(record["pre"],name,16)[8:]==raw_checker.register_raw(record["post"],name,16)[8:],"register MOVSD high lane preserved")
                    elif destination["width"]==4:
                        require(not any(raw_checker.register_raw(record["post"],keyname,8)[4:]),"GPR zero extension")
                        for i in range(4,8):knowledge["r",keyname,i]=0
            if opcode=="xor" and len(args)==2 and args[0]==args[1] and ops:
                operand=ops[-1];data=raw_checker.register_raw(record["post"],operand["register"],operand["width"])
                require(not any(data),"integer xor zero")
                name=raw_checker.operand_keys(operand)[0][1];exempt.add(name)
                for i in range(8 if operand["width"]==4 else operand["width"]):knowledge["r",name,i]=0
            for name in record["pre"]["gpr"]:
                if name not in exempt and record["pre"]["gpr"][name]!=record["post"]["gpr"][name]:
                    for i in range(8):knowledge.pop(("r",name,i),None)
        for name,address in region["pointers"].items():
            for i,byte in enumerate(raw_checker.raw(region["end_state"][name],16)):
                require(knowledge.get(("m",address+i))==byte,"buffer endpoint not explained by captured writes")


class _Reconstruction(storage._Reconstruction):
    def __init__(self, rows, capture, decoded, native):
        super().__init__(rows, capture, decoded)
        self.native = native

    def native_row(self, row, region, stack_bytes):
        sidecar = self.native[row['seq']]
        _native_numeric(row, sidecar)
        handled = set()
        if row['elf_address'] == 0x1996C4:
            destination = row['operands'][1]
            value_id = f"v:r{row['seq']}:zero"
            self.add_value({'value_id': value_id, 'producer_kind': 'ZERO_BITS', 'raw_bits': '0x' + '00' * 32,
                'width': 32, 'producer': {'role': 'zero_result', 'trace_sequence': row['seq'],
                    'operand_index': 1, 'phase': row['phase']},
                'storage': {'space': 'register', 'name': 'v16', 'byte_offset': 0, 'width': 32}, 'source_slices': []})
            self.assign(destination, value_id, range(32))
            handled.update(storage._operand_keys(destination))
            for offset in range(32, 64):
                self.state.pop(('r', 'v16', offset), None)
        elif row['elf_address'] == 0x199720:
            source, destination = row['operands']
            refs = self.refs_for(source)
            require(len(refs) == 16 and all(ref is not None for ref in refs), 'native masked store provenance missing')
            source_bytes = bytes.fromhex(sidecar['before']['vectors']['zmm16'])[:16]
            for offset, ref in enumerate(refs):
                value = self.value_by_id[ref[0]]
                require(storage._raw_bytes(value['raw_bits'], value['width'], 'native source provenance')[ref[1]] == source_bytes[offset],
                        'native masked store provenance bytes')
            # The audited copy formatter receives only pre-vector bits already
            # independently compared with the recorded result; rows stay intact.
            self.add_copy(row, region, stack_bytes, source, destination, 0, 1)
            handled.update(storage._operand_keys(destination))
        self.invalidate_unhandled_changes(row, handled)

    def run(self) -> tuple[list[dict], list[dict]]:
        for region_index, original_region in enumerate(self.capture["regions"]):
            region = dict(original_region)
            subset = self.rows[region["start_seq"] : region["end_seq"]]
            region["_first"] = subset[0]
            region["_entry_rsp"] = subset[0]["pre"]["gpr"]["rsp"]
            stack_bytes = self.stack_bytes(subset)
            self.state = {}
            if region_index == 0:
                for name in storage.BOUNDARIES:
                    self.boundary_value(region, name, "LOAD_BITS")
            else:
                storage._require(bool(self.init_endpoint), "missing init endpoint provenance")
                for name in storage.LINKED_BOUNDARIES:
                    base = original_region["pointers"][name]
                    refs = [self.init_endpoint.get(("m", base + offset)) for offset in range(16)]
                    storage._require(all(ref is not None for ref in refs), f"missing init endpoint for {name}")
                    self.boundary_value(region, name, "COPY_BITS", refs)
                self.boundary_value(region, "gradient", "LOAD_BITS")
            for name in ("xmm0", "xmm1"):
                self.boundary_value(region, name, "LOAD_BITS")

            for row in subset:
                if row["seq"] in self.native:
                    self.native_row(row, region, stack_bytes)
                    continue
                reference = self.decoded[row["module_path"], row["elf_address"]]
                try:
                    opcode, decoded_kind, _args, _width = decode(reference)
                except DecodeRefused as exc:
                    storage._fail(f"row {row['seq']} independent decode refused: {exc}")
                storage._require(
                    row["kind"] == decoded_kind,
                    f"row {row['seq']} recorded kind disagrees with decoded kind",
                )
                handled: set[tuple] = set()
                if decoded_kind in {"ADD", "SUB", "MUL"}:
                    storage._require(opcode in storage.ARITHMETIC_KINDS, f"row {row['seq']} unsupported scalar opcode")
                    self.add_arithmetic(row, region, stack_bytes, opcode)
                    handled.update(storage._operand_keys(row["operands"][1]))
                elif decoded_kind in {"MOVE", "STACK"}:
                    storage._require(len(row["operands"]) == 2, f"row {row['seq']} copy operand count")
                    source, destination = row["operands"]
                    self.add_copy(row, region, stack_bytes, source, destination, 0, 1)
                    self.add_zero_extend(row, destination, 1)
                    self.add_zero_upper(row, destination, 1, opcode)
                    handled.update(storage._operand_keys(destination))
                    if destination["kind"] == "register" and destination["width"] == 4:
                        name = storage._canonical_register(destination["register"])
                        handled.update(("r", name, offset) for offset in range(4, 8))
                    if destination["kind"] == "register" and storage._canonical_register(
                        destination["register"]
                    ).startswith("v"):
                        handled.update(("r", storage._canonical_register(destination["register"]), offset) for offset in range(16))
                elif decoded_kind in {"ZERO", "ZERO_FILL"}:
                    destination = row["operands"][-1]
                    self.add_vector_zero(row, destination, len(row["operands"]) - 1)
                    handled.update(storage._operand_keys(destination))
                elif opcode == "xor" and len(row["operands"]) == 2:
                    first, destination = row["operands"]
                    if (
                        first["kind"] == destination["kind"] == "register"
                        and first["register"] == destination["register"]
                    ):
                        self.add_integer_zero(row, destination, 1)
                        handled.update(storage._operand_keys(destination))
                self.invalidate_unhandled_changes(row, handled)

            if region_index == 0:
                self.init_endpoint = dict(self.state)
            for name, base in original_region["pointers"].items():
                expected = storage._raw_bytes(original_region["end_state"][name], 16, "region endpoint")
                for offset, byte in enumerate(expected):
                    ref = self.state.get(("m", base + offset))
                    storage._require(ref is not None, f"buffer endpoint provenance missing: {region['phase']} {name}")
                    producer = self.value_by_id[ref[0]]
                    actual = storage._raw_bytes(producer["raw_bits"], producer["width"], "producer bits")[
                        ref[1]
                    ]
                    storage._require(actual == byte, f"buffer endpoint bits mismatch: {region['phase']} {name}")
        return self.operations, self.values


def graph(capture, rows, regions, root, verified_spans):
    """Return canonical operations, values and storage state without producer code."""
    selected, graph_rows = deepcopy(regions), deepcopy(rows)
    native = _native_spans(graph_rows, selected, verified_spans)
    for region in selected:
        region['phase'] = region['occurrence']
        for field in ('start_state', 'end_state'):
            region[field] = {name: '0x' + ''.join(x[2:] for x in reversed(lanes)) for name, lanes in region[field].items()}
        for row in graph_rows[region['start_seq']:region['end_seq']]:
            row['phase'] = region['phase']
    subcapture = {**capture, 'regions': selected}
    body = [row for region in selected for row in graph_rows[region['start_seq']:region['end_seq']]]
    for region in selected:
        subset = graph_rows[region['start_seq']:region['end_seq']]
        require(subset and subset[0]['runtime_pc'] == region['entry_pc'] and subset[-1]['post_pc'] == region['return_pc'],
                'complete graph region entry/exit')
        for offset, row in enumerate(subset):
            require(row['seq'] == region['start_seq'] + offset and row['ptid'] == subset[0]['ptid'], 'graph dense owner rows')
            if offset:
                previous = subset[offset - 1]
                require(previous['post_pc'] == row['runtime_pc'], 'graph PC continuity')
                for field in ('gpr', 'xmm', 'mxcsr', 'eflags', 'segment_bases'):
                    require(previous['post'][field] == row['pre'][field], 'graph projected state continuity')
    for row in body:
        if row['seq'] not in native:
            audited.check_control_ea(row)
        for operand in row['operands']:
            if operand['kind'] == 'memory':
                audited.module_operand(operand['address'], operand['width'], capture['modules'])
    decoded = raw_checker.disassembly_for_rows(body, capture['modules'], root=root)
    _verify_flow(graph_rows, subcapture, decoded, root=root, native=native)
    reconstruction = _Reconstruction(graph_rows, subcapture, decoded, native)
    operations, values = reconstruction.run()
    for operation in operations:
        audited.check_ieee(operation['operation_kind'], operation['input0_raw_bits'],
                           operation['input1_raw_bits'], operation['output_raw_bits'])
    return operations, values, reconstruction.state

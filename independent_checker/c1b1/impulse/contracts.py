from dataclasses import dataclass
from fractions import Fraction as Q
from .wire import parse, integer, HASH_RE, WireFailure


class ContractFailure(Exception):
    def __init__(self, reason='SCHEMA_INVALID', phase='PARSE', kind=None):
        self.reason, self.phase, self.kind = reason, phase, kind
        super().__init__(reason)


@dataclass(frozen=True)
class ParsedInput:
    obj: dict
    q: tuple
    q_raw: tuple
    budget: dict


def validate_input(data, spec):
    try:
        obj=parse(data)
        keys=spec.wire['closed_object_keys']
        def closed(value, kind):
            if type(value) is not dict or set(value)!=set(keys[kind]):
                raise ContractFailure()
        def hash_value(value):
            if type(value) is not str or not HASH_RE.fullmatch(value):
                raise ContractFailure()
        closed(obj,'Input')
        if obj['schema']!='LAB_C1B1_IMPULSE_INPUT_V1': raise ContractFailure()
        hash_value(obj['spec_sha256'])
        if obj['spec_sha256']!=spec.sha256: raise ContractFailure('BINDING_MISMATCH','BINDING')
        state=obj['state'];closed(state,'State')
        for name,frac in [('position_grid','48'),('momentum_grid','80')]:
            closed(state[name],'Grid')
            if state[name]!={'kind':'FX','width':'96','frac_bits':frac}:raise ContractFailure()
        atoms=state['atoms']
        if type(atoms) is not list or len(atoms)!=2:raise ContractFailure()
        positions=[]
        for atom in atoms:
            closed(atom,'Atom');hash_value(atom['atom_id'])
            if atom['species']!='Ar40':raise ContractFailure()
            for name in ['position_raw','momentum_raw']:
                if type(atom[name]) is not list or len(atom[name])!=3:raise ContractFailure()
                values=tuple(integer(v) for v in atom[name])
                if any(not -(1<<95)<=v<1<<95 for v in values):raise ContractFailure()
                if name=='position_raw':positions.append(values)
        if atoms[0]['atom_id']==atoms[1]['atom_id']:raise ContractFailure()
        acq=obj['acquisition'];closed(acq,'Acquisition')
        for name in ['record_id','acquisition_id','executor_source_sha256','acquisition_tool_sha256']:hash_value(acq[name])
        if acq['full_half']!='HALF_OF_FULL_DT' or acq['phase'] not in ['FIRST_HALF_KICK','SECOND_HALF_KICK']:raise ContractFailure()
        if acq['phase']=='FIRST_HALF_KICK':
            if acq['previous_occurrence_sha256'] is not None:raise ContractFailure()
        else:hash_value(acq['previous_occurrence_sha256'])
        budget=obj['budget'];closed(budget,'Budget')
        parsed={}
        for name in keys['Budget']:
            if name in ['basis_record_sha256','issuer_sha256']:hash_value(budget[name])
            elif name=='profile_version':
                if budget[name]!='1':raise ContractFailure()
            else:parsed[name]=integer(budget[name],positive=True)
        if parsed['N0']<1 or parsed['P0']<8 or parsed['N_max']<parsed['N0'] or parsed['P_max']<parsed['P0']:
            raise ContractFailure()
        if parsed['input_parse_bytes']>1048576 or parsed['private_certificate_bytes']>1048576:
            raise ContractFailure()
        qraw=tuple(b-a for a,b in zip(*positions))
        return ParsedInput(obj,tuple(Q(v,1<<48) for v in qraw),qraw,parsed)
    except WireFailure as err:
        raise ContractFailure(err.reason,'PARSE',err.kind) from None

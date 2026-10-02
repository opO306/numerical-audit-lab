"""Pinned array-gradient N=1 arithmetic order; no algebraic rewriting."""
from fractions import Fraction

from numeric_core import Binary64Finite, Exact, Instr, run

GRAD_ADDR=('1cb85','1cb89','1cb8d','1cb91','1cb95','1cba3','1cba7','1cbac','1cbb0')

def constants():
    return [Instr('CONST','dt',('1/64',)),Instr('CONST','half',('1/2',)),Instr('CONST','gz',(0,))]

def gradient(x,y,t):
    I=Instr
    return [I('MUL','xy'+t,(y,x)),I('ADD','ax'+t,('gz',x)),
            I('MUL','xx'+t,(x,x)),I('ADD','dbl'+t,('xy'+t,'xy'+t)),
            I('ADD','gx'+t,('dbl'+t,'ax'+t)),I('MUL','yy'+t,(y,y)),
            I('ADD','ay'+t,(y,'gz')),I('SUB','diff'+t,('xx'+t,'yy'+t)),
            I('ADD','gy'+t,('diff'+t,'ay'+t))]

def init_program():
    I=Instr
    return constants()+gradient('x','y','i')+[I('MUL','hhalf',('dt','half')),
        I('MUL','kx',('gxi','hhalf')),I('SUB','vhx',('vx','kx')),
        I('MUL','ky',('gyi','hhalf')),I('SUB','vhy',('vy','ky'))]

def step_program():
    I=Instr
    return constants()+[I('MUL','dx',('dt','vhx')),I('ADD','x1',('dx','x')),
        I('MUL','dy',('dt','vhy')),I('ADD','y1',('dy','y'))]+gradient('x1','y1','s')+[
        I('MUL','hhalf',('dt','half')),I('MUL','kx',('gxs','hhalf')),I('SUB','vox',('vhx','kx')),
        I('MUL','gdx',('dt','gxs')),I('SUB','vhx1',('vhx','gdx')),
        I('MUL','ky',('gys','hhalf')),I('SUB','voy',('vhy','ky')),
        I('MUL','gdy',('dt','gys')),I('SUB','vhy1',('vhy','gdy'))]

def structure(p):
    return [(i.op,i.dst,i.args if i.op!='CONST' else (),str(i.args[0]) if i.op=='CONST' else None) for i in p]

def addresses(phase):
    if phase=='init':
        return [None]*3+list(GRAD_ADDR)+['15941','15993','15997','15993','15997']
    if phase=='step':
        return [None]*3+['1580b','15818','1580b','15818']+list(GRAD_ADDR)+[
            '15855','1588e','15892','158a1','158ac','1588e','15892','158a1','158ac']
    raise ValueError('unsupported phase')

def assert_machine_structure(s,phase):
    expected=structure(init_program() if phase=='init' else step_program() if phase=='step' else [])
    if not expected or list(s)!=expected:
        raise ValueError('trace differs from sealed machine arithmetic contract')

class BinaryReplay:
    def __init__(self,exact=False):
        self.exact=exact;self.prof=Exact() if exact else Binary64Finite()
        self.init_p,self.step_p=init_program(),step_program()
        self.init_structure,self.step_structure=structure(self.init_p),structure(self.step_p)

    def _run(self,p,inputs):
        r=run(p,self.prof,inputs)
        if r.halt:raise RuntimeError(f'VM halted: {r.halt}')
        return {k:Fraction(v) if self.exact else int(v,16) for k,v in r.registers.items()}

    def init(self,x,y,vx,vy):
        return self._run(self.init_p,dict(x=x,y=y,vx=vx,vy=vy))

    def step(self,x,y,vhx,vhy):
        return self._run(self.step_p,dict(x=x,y=y,vhx=vhx,vhy=vhy))

    def trace(self,phase,regs):
        if self.exact:raise ValueError('binary trace requires bit registers')
        s=self.init_structure if phase=='init' else self.step_structure
        assert_machine_structure(s,phase)
        return [{'ordinal':i,'op':op,'dst':dst,'args':list(args),'literal':lit,
                 'operand_bits':[f'{regs[a]:016x}' for a in args],
                 'result_bits':f'{regs[dst]:016x}','machine_address':address,
                 'instruction_occurrence':f'{address}:{i}' if address else 'load/initialization'}
                for i,((op,dst,args,lit),address) in enumerate(zip(s,addresses(phase)))]

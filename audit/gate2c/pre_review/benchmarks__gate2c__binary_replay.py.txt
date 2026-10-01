"""Explicit 2D instruction order from the frozen gala disassembly.

This is a post-diagnostic model, not a blind prediction of gala output.
All operations run through the existing numeric_core VM.
"""
from fractions import Fraction

from numeric_core import Binary64Finite, Exact, Instr, run


def constants():
    return [Instr('CONST','dt',('1/64',)), Instr('CONST','half',('1/2',)),
            Instr('CONST','gz',(0,)), Instr('MUL','hhalf',('dt','half'))]


def gradient(x,y,t):
    I=Instr
    return [I('ADD','ax'+t,('gz',x)), I('ADD','dbl'+t,(x,x)),
            I('MUL','xy'+t,('dbl'+t,y)), I('ADD','gx'+t,('ax'+t,'xy'+t)),
            I('MUL','xx'+t,(x,x)), I('MUL','yy'+t,(y,y)),
            I('SUB','diff'+t,('xx'+t,'yy'+t)), I('ADD','ay'+t,('gz',y)),
            I('ADD','gy'+t,('diff'+t,'ay'+t))]


def init_program():
    I=Instr
    return constants()+gradient('x','y','i')+[
        I('MUL','kx',('gxi','hhalf')),I('SUB','vhx',('vx','kx')),
        I('MUL','ky',('gyi','hhalf')),I('SUB','vhy',('vy','ky'))]


def step_program():
    I=Instr
    return constants()+[
        I('MUL','dx',('dt','vhx')),I('ADD','x1',('x','dx')),
        I('MUL','dy',('dt','vhy')),I('ADD','y1',('y','dy'))]+gradient('x1','y1','s')+[
        I('MUL','kx',('gxs','hhalf')),I('SUB','vox',('vhx','kx')),
        I('MUL','gdx',('dt','gxs')),I('SUB','vhx1',('vhx','gdx')),
        I('MUL','ky',('gys','hhalf')),I('SUB','voy',('vhy','ky')),
        I('MUL','gdy',('dt','gys')),I('SUB','vhy1',('vhy','gdy'))]


def structure(p):
    return [(i.op,i.dst,i.args if i.op!='CONST' else (),str(i.args[0]) if i.op=='CONST' else None) for i in p]


class BinaryReplay:
    def __init__(self, exact=False):
        self.exact=exact
        self.prof=Exact() if exact else Binary64Finite()
        self.init_p,self.step_p=init_program(),step_program()
        self.init_structure,self.step_structure=structure(self.init_p),structure(self.step_p)

    def _run(self,p,inputs):
        r=run(p,self.prof,inputs)
        if r.halt:
            raise RuntimeError(f'VM halted: {r.halt}')
        return {k:Fraction(v) if self.exact else int(v,16) for k,v in r.registers.items()}

    def init(self,x,y,vx,vy):
        return self._run(self.init_p,dict(x=x,y=y,vx=vx,vy=vy))

    def step(self,x,y,vhx,vhy):
        return self._run(self.step_p,dict(x=x,y=y,vhx=vhx,vhy=vhy))

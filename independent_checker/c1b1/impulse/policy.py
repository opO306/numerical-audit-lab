"""Internal author reference controls. Not an issued/approved runtime Budget."""
from dataclasses import dataclass
from .resource import ResourceAccount, ResourceLimit, AUTHOR_ALLOCATION_BASIS


@dataclass(frozen=True)
class ReferencePolicy:
    N0: int
    P0: int
    N_max: int
    P_max: int
    max_attempts: int
    exp_order_max: int
    integer_bit_max: int
    rational_num_bit_max: int
    rational_den_bit_max: int
    work_unit_max: int
    private_certificate_bytes: int
    legacy_sqrt_bits_max: int
    legacy_work_bits_max: int
    legacy_order_max: int
    temporary_allocation_bytes: int
    live_allocation_bytes: int

    def __post_init__(self):
        if any(type(v) is not int or v <= 0 for v in vars(self).values()):
            raise ValueError('invalid finite author controls')
        if self.P0<8 or self.N_max<self.N0 or self.P_max<self.P0 or self.private_certificate_bytes>1048576:
            raise ValueError('invalid reference schedule')

    def account(self):
        return ResourceAccount(bit_max=self.integer_bit_max,num_bit_max=self.rational_num_bit_max,
            den_bit_max=self.rational_den_bit_max,work_max=self.work_unit_max,
            allocation_basis=AUTHOR_ALLOCATION_BASIS,temp_max=self.temporary_allocation_bytes,
            live_max=self.live_allocation_bytes)

    def attempts(self):
        n,p=self.N0,self.P0
        for t in range(self.max_attempts):
            if n>self.N_max or p>self.P_max:
                raise ResourceLimit('BIT')
            yield t,n,p
            if t+1<self.max_attempts:
                if n>self.N_max//2 or p>self.P_max//2:
                    raise ResourceLimit('BIT')
                n*=2;p*=2

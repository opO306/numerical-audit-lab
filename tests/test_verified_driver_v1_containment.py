"""Real controller termination with marker-only subprocess groups."""
from pathlib import Path
import json, os, signal, subprocess, sys, time
import pytest
from verified_driver.v1.containment import ContainedLiveProcess
from tests.verified_driver_v1_support import ROOT

def until(predicate,seconds=8):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        if predicate(): return
        time.sleep(.01)
    raise AssertionError('required process evidence did not arrive')

CONTROLLER='''
import sys,time
from pathlib import Path
from verified_driver.v1.containment import ContainedLiveProcess
root=Path(sys.argv[1]); worker=sys.argv[2]; mode=sys.argv[3]
p=ContainedLiveProcess([sys.executable,worker,str(root),mode],cwd=Path.cwd(),
    env=None,pass_fds=(),stdout=None,stderr=None,receipt=root/'containment.json')
(root/'controller-ready').write_text(str(p.pid))
while True: time.sleep(1)
'''
WORKER='''
import os,sys,time,subprocess
from pathlib import Path
root=Path(sys.argv[1]); mode=sys.argv[2]
child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'])
(root/'pids.json').write_text(__import__('json').dumps([os.getpid(),child.pid]))
(root/mode).write_text('TEST_ONLY')
if mode=='paused': time.sleep(30)
else: time.sleep(1)
(root/'next-body').write_text('UNAUTHORIZED')
time.sleep(30)
'''

@pytest.mark.parametrize('mode',['paused','active'])
def test_actual_controller_sigkill_stops_complete_child_group(tmp_path,mode):
    worker=tmp_path/'worker.py'; worker.write_text(WORKER)
    controller=subprocess.Popen([sys.executable,'-c',CONTROLLER,str(tmp_path),str(worker),mode],cwd=ROOT)
    try:
        until(lambda:(tmp_path/mode).exists() and (tmp_path/'controller-ready').exists())
        os.kill(controller.pid,signal.SIGKILL); controller.wait(timeout=5)
        until(lambda:(tmp_path/'containment.json').exists())
        receipt=json.loads((tmp_path/'containment.json').read_bytes())
        assert receipt['reason']=='CONTROLLER_PIPE_EOF'
        pids=json.loads((tmp_path/'pids.json').read_bytes())
        assert set(pids).issubset(receipt['group_pids_before_stop'])
        assert receipt['group_remaining_pids']==[]
        assert receipt['controller_pid']==controller.pid
        assert not (tmp_path/'next-body').exists()
        assert all(not Path('/proc',str(pid)).exists() for pid in pids)
    finally:
        if controller.poll() is None: controller.kill(); controller.wait(timeout=5)

def test_explicit_termination_has_a_real_execution_receipt(tmp_path):
    p=ContainedLiveProcess([sys.executable,'-c','import time; time.sleep(30)'],cwd=ROOT,
        env=None,pass_fds=(),stdout=None,stderr=None,receipt=tmp_path/'stop.json')
    p.terminate_group('unit shutdown')
    receipt=json.loads((tmp_path/'stop.json').read_bytes())
    assert receipt['group_remaining_pids']==[] and p.poll() is not None

def test_live_session_launcher_is_contained_and_explicit_stop_reaps_group(tmp_path):
    from tests.test_live_chain_session import FixtureSession
    from tests.verified_driver_v1_support import LEDGER
    session=FixtureSession(ROOT,tmp_path/'session',3,LEDGER)
    try:
        session.start()
        assert isinstance(session.process,ContainedLiveProcess)
        session.terminate('controlled launcher stop')
        receipt=json.loads((session.run_root/'containment.json').read_bytes())
        assert receipt['group_remaining_pids']==[]
        assert not (session.run_root/'body2').exists()
    finally: session.terminate('test cleanup')

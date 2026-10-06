"""Separate producer/checker processes; checker branch never imports producer."""
import argparse
from pathlib import Path
from verified_driver.v1.model import ChainState, strict_json

def main():
    p=argparse.ArgumentParser(); p.add_argument('mode',choices=('produce','check'))
    for name in ('checkpoint','predecessor','out','root','report'): p.add_argument('--'+name,required=True,type=Path)
    a=p.parse_args(); pred=ChainState(**strict_json(a.predecessor.read_bytes()))
    if a.mode=='produce':
        from .producer import build_edge
        build_edge(a.checkpoint,pred,a.out,a.root)
    else:
        from .checker import check_edge
        result=check_edge(a.checkpoint,a.out,pred,a.root,a.report)
        return 0 if result['verdict']=='CHECKER_PASS' else 2
    return 0
if __name__=='__main__': raise SystemExit(main())

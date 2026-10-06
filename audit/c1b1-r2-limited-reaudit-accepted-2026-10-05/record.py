"""Record received independent verdict and freshly observed provenance."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'current/c1b1-r2-limited-reaudit-accepted-2026-10-05'
TARGET = '79a655f0848152aa765e1537b741518b2fa97acf'
PARENT = 'baba8ea942b896af64ceaa7ab41e2bc5db73112c'
BRANCH = 'codex/c1b1-fclaim1-output-limit'
BUNDLE = '4bd5cb0ef00c022689aa1a1dd4354deba08961ab4e1887b38d2f62f287a8cced'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, obj):
    path = OUT / name
    assert not path.exists(), 'refusing overwrite: ' + name
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=True)+'\n', encoding='ascii')


commands = []


def git(*args):
    run = subprocess.run(['git', *args], cwd=ROOT, capture_output=True)
    commands.append(dict(command=['git', *args], exit=run.returncode,
                         stdout=run.stdout.decode('utf8'), stderr=run.stderr.decode('utf8')))
    assert run.returncode == 0
    return run.stdout.decode('utf8').strip()


assert git('rev-parse', 'HEAD') == TARGET
assert git('rev-parse', 'HEAD^') == PARENT
assert git('branch', '--show-current') == BRANCH
assert not git('diff', '--name-only') and not git('diff', '--cached', '--name-only')
metadata = git('show', '-s', '--format=%H%n%P%n%cI%n%s', 'HEAD').splitlines()
assert metadata == [TARGET, PARENT, '2026-10-05T14:41:41+09:00',
                    'Account impulse radius arithmetic within the work budget']
tracking = git('rev-parse', 'refs/remotes/origin/'+BRANCH)
remote = git('ls-remote', '--heads', 'origin', 'refs/heads/'+BRANCH)
assert tracking == TARGET and remote.split() == [TARGET, 'refs/heads/'+BRANCH]
sources = {p.name: sha(p) for p in sorted((ROOT/'independent_checker/c1b1/impulse').glob('*.py'))}
bundle = hashlib.sha256((json.dumps(sources, sort_keys=True, separators=(',', ':'), ensure_ascii=True)+'\n').encode('ascii')).hexdigest()
assert len(sources) == 18 and bundle == BUNDLE
old_receipt_path = ROOT/'current/c1b1-r2-precharge-fix-2026-10-05/receipt.json'
receipt = json.loads(old_receipt_path.read_text(encoding='utf8'))
assert receipt['candidate_source_bundle_sha256'] == BUNDLE
assert len(receipt['evidence_files']) == 185
for path, identity in receipt['evidence_files'].items():
    assert sha(ROOT/path) == identity['sha256'] and (ROOT/path).stat().st_size == identity['bytes'], path
previous = json.loads((OUT/'previous-author-turn-metadata.json').read_text(encoding='utf8'))
assert previous['completedAt'] == 1791178880
assert previous['completionUTC'] == '2026-10-05T05:41:20.000Z'
assert previous['lastAgentMessage']['phase'] == 'final_answer'
commit_time = datetime.fromisoformat(metadata[2]).astimezone(timezone.utc)
completion_time = datetime.fromtimestamp(previous['completedAt'], timezone.utc)
seconds = int((commit_time-completion_time).total_seconds())
assert seconds == 21
paths = git('ls-files', '-z').split('\0')
paths = [p for p in paths if p]
save('observed-provenance.json', dict(
    schema='C1B1_R2_LIMITED_REAUDIT_ACCEPTANCE_PROVENANCE_V1', observed_at_utc=datetime.now(timezone.utc).isoformat(),
    target=TARGET, parent=PARENT, branch=BRANCH, commit_recorded_time=metadata[2], commit_subject=metadata[3],
    local_origin_tracking=tracking, live_origin_branch=remote,
    source_bundle_sha256=BUNDLE, source_files=sources,
    author_receipt_verification=dict(path=old_receipt_path.relative_to(ROOT).as_posix(), sha256=sha(old_receipt_path),
                                    evidence_files=185, mismatches=[]),
    previous_author_turn=dict(source=previous['source'], turn_id=previous['turnId'],
                             completed_at_unix=previous['completedAt'], completed_at_utc=previous['completionUTC'],
                             completed_at_kst='2026-10-05T14:41:20+09:00',
                             final_message_id=previous['lastAgentMessage']['id']),
    timing=dict(commit_recorded_after_previous_author_turn_completion_seconds=seconds,
                forwarded_report_time_kst_as_reported_by_user='2026-10-05T14:42:00+09:00',
                commit_recorded_before_report_forwarding_seconds_as_reported=19,
                local_turn_completion_is_not_the_external_report_forwarding_timestamp=True,
                exact_push_time='UNRESOLVED', commit_push_actor='UNRESOLVED', authorization_path='UNRESOLVED'),
    received_verdict_source='USER-PROVIDED CHAT MESSAGE; supplied text retained as a UTF-8 transcription from read_thread',
    received_message_sha256=sha(OUT/'USER_PROVIDED_REAUDIT_KO.md'),
    received_independent_results=dict(ROUND_ADD='LIMITED INDEPENDENT REAUDIT PASS',
                                     QDIV_SIGN='LIMITED INDEPENDENT REAUDIT PASS',
                                     R2_PRECHARGE='LIMITED INDEPENDENT REAUDIT PASS / FINDING CLOSED',
                                     W3='INDEPENDENTLY REPRODUCED', full_pytest='1136 passed in 45.55s', static_spec='155 PASS'),
    author_reexecuted_independent_probe=False, author_reexecuted_full_pytest_this_turn=False,
    new_arithmetic_patch=False, implementation_changed=False, commit_performed_this_turn=False, push_performed_this_turn=False,
    global_resource_accounting='NOT PASS', reference_producer_implementation='NOT YET INDEPENDENTLY APPROVED',
    runtime_activation_allowed=False, J_status='J_NOT_VERIFIED', certification='NotCertified',
    baseline_working_sha256={p:sha(ROOT/p) for p in paths}, commands=commands,
    role='AUTHOR PROVENANCE CHECK AND RECEIPT OF A USER-SUPPLIED INDEPENDENT VERDICT; NOT A NEW AUTHOR INDEPENDENT AUDIT'))
print('VERIFIED current local/remote target; 18-source bundle; historical receipt185; previous turn timing')
print('SOURCE', BUNDLE, 'COMMIT RECORD AFTER PRIOR TURN', seconds, 'seconds; actor/approval unresolved')

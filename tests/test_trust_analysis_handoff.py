import copy
import pytest
from test_convert_behavior import trust_row, write_delimited
from convert_behavior import convert_source, _format_value
from trust_analysis_handoff import schema_check, compare_extension


def event_rows(tmp_path):
    p=tmp_path/'trust.csv'
    write_delimited(p,[trust_row(), trust_row(TrialNumber=2,onset=20,resp=0,cLeft=0,cRight=2,highlow='low')])
    return [{k:_format_value(v) for k,v in r.items()} for r in convert_source('trust',p).rows]


def test_extension_preserves_old_columns_and_zero_feedback(tmp_path):
    rows=event_rows(tmp_path)
    old=[{k:v for k,v in r.items() if k not in {'scheduled_reciprocation','cLeft','cRight'}} for r in rows]
    assert compare_extension(old,rows)==1
    rows[0]['choice']='low'
    with pytest.raises(ValueError,match='historical choice'):compare_extension(old,rows)


def test_misaligned_outcome_schedule_rejected(tmp_path):
    rows=event_rows(tmp_path);rows[1]['reciprocate']='defect'
    with pytest.raises(ValueError,match='observed/scheduled'):schema_check(rows)


def test_zero_choice_cannot_acquire_feedback(tmp_path):
    rows=event_rows(tmp_path);invented=copy.deepcopy(rows[-1])
    invented.update(trial_type='outcome_friend_recip',reciprocate='recip');rows.append(invented)
    with pytest.raises(ValueError,match='zero choice'):schema_check(rows)


def test_old_snapshot_with_empty_imaging_templates_reuses_original_evidence(tmp_path):
    import json
    from pathlib import Path
    from trust_analysis_handoff import read, write, canonical_trust_files, check_snapshot_events
    rows=event_rows(tmp_path)
    rel='sub-10953/ses-01/func/sub-10953_ses-01_task-trust_run-1_events.tsv'
    path=tmp_path/'bids'/rel
    write(path,rows,list(rows[0]))
    old=[{k:v for k,v in row.items() if k not in {'scheduled_reciprocation','cLeft','cRight'}} for row in rows]
    saved={'events':{rel:old}}
    for part in ['mag','phase']:
        template=path.with_name(path.name.replace('_events.tsv',f'_part-{part}_events.tsv'))
        template.write_text('onset\tduration\ttrial_type\tTODO -- fill in rows\n')
        saved['events'][str(template.relative_to(tmp_path/'bids'))]=[]
    original=json.dumps(saved,sort_keys=True)
    assert canonical_trust_files(tmp_path/'bids')==[path]
    zeros,canonical,ignored=check_snapshot_events(saved,tmp_path/'bids')
    assert zeros==1 and list(canonical)==[rel] and len(ignored)==2
    assert json.dumps(saved,sort_keys=True)==original
    assert read(path)==rows


@pytest.mark.parametrize('populated_before',[False,True])
def test_nonempty_imaging_template_is_never_silently_discarded(tmp_path,populated_before):
    from trust_analysis_handoff import canonical_trust_files, canonical_snapshot_events
    root=tmp_path/'bids';folder=root/'sub-10953/ses-01/func';folder.mkdir(parents=True)
    path=folder/'sub-10953_ses-01_task-trust_run-1_part-mag_events.tsv'
    path.write_text('onset\tduration\n'+('' if populated_before else '0\t1\n'))
    saved={'events':{str(path.relative_to(root)):[{'onset':'0','duration':'1'}] if populated_before else []}}
    with pytest.raises(ValueError,match='nonempty noncanonical'):
        canonical_snapshot_events(saved,root)
    if not populated_before:
        with pytest.raises(ValueError,match='nonempty noncanonical'):
            canonical_trust_files(root)


def test_missing_canonical_schema_still_fails_with_filename(tmp_path):
    from trust_analysis_handoff import write, check_snapshot_events
    rel='sub-10953/ses-01/func/sub-10953_ses-01_task-trust_run-1_events.tsv'
    rows=[{k:v for k,v in row.items() if k not in {'scheduled_reciprocation','cLeft','cRight'}} for row in event_rows(tmp_path)]
    write(tmp_path/rel,rows,list(rows[0]))
    with pytest.raises(ValueError,match='sub-10953.*Trust schema additions are missing'):
        check_snapshot_events({'events':{rel:rows}},tmp_path)


def test_validation_check_only_never_converts_or_snapshots(tmp_path):
    import os
    import subprocess
    from pathlib import Path
    import trust_analysis_handoff
    root=tmp_path/'project';(root/'code').mkdir(parents=True);bin_dir=tmp_path/'bin';bin_dir.mkdir()
    source=Path(trust_analysis_handoff.__file__).with_name('run_trust_handoff.sh')
    script=root/'code/run_trust_handoff.sh';script.write_text(source.read_text())
    calls=tmp_path/'calls'
    fake_python=bin_dir/'python3'
    fake_python.write_text('''#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$HANDOFF_CALLS"
if [[ "$1" == code/trust_analysis_handoff.py ]]; then
  [[ "$2" == check ]] || exit 91
elif [[ "$1" == - ]]; then
  cat >/dev/null
fi
''')
    for name,body in [('git','#!/bin/sh\nexit 0\n'),('make','#!/bin/sh\nexit 0\n')]:
        p=bin_dir/name;p.write_text(body);p.chmod(0o755)
    fake_python.chmod(0o755)
    env=dict(os.environ,PATH=str(bin_dir)+os.pathsep+os.environ['PATH'],HANDOFF_CALLS=str(calls))
    result=subprocess.run(['bash',str(script),'validation','--check-only'],env=env,text=True,capture_output=True)
    assert result.returncode==0,result.stdout+result.stderr
    assert 'check --scope validation' in calls.read_text()
    assert 'snapshot' not in calls.read_text()
    assert not (root/'work/trust_schema/validation.json').exists()


def plan_fixture(tmp_path, *, short=False):
    from pathlib import Path
    from test_convert_behavior import write_bold
    from convert_behavior import RunKey
    bids=tmp_path/'bids';behavior=tmp_path/'private'
    for sub,run in [('10001',1),('10001',2),('10002',1)]:
        write_bold(bids,RunKey(sub,'01','trust',run))
    raw=behavior/'Scan-Investment_Game/logs/10001/sub-10001_task-trust_run-0_raw.csv'
    rows=[trust_row(TrialNumber=i+1,onset=10+i*10,ISI_onset=13+i*10,outcome_onset=15+i*10,outcome_offset=17+i*10) for i in range(11 if short else 42)]
    write_delimited(raw,rows)
    malformed=raw.with_name('sub-10001_task-trust_run-1_raw.csv')
    write_delimited(malformed,rows)
    with malformed.open('a') as f:f.write(','.join(rows[0])+'\n')
    curation=tmp_path/'curation.tsv'
    curation.write_text('subject\tsession\ttask\trun\tissue\tsource_sha256\ttrial_fingerprint\treviewer\tnote\n')
    return bids,behavior,curation,raw


def test_plan_excludes_unresolved_runs_and_retains_other_run(tmp_path):
    from trust_analysis_handoff import cohort_run_plan
    from convert_behavior import convert_behavior
    bids,behavior,curation,raw=plan_fixture(tmp_path)
    rows=cohort_run_plan(bids,behavior,set(),curation,['10001','10002'])
    ready=[r for r in rows if r['conversion_status']=='ready']
    excluded=[r for r in rows if r['conversion_status']=='excluded']
    assert [(r['participant_id'],r['run']) for r in ready]==[('sub-10001',1)]
    assert any(r['exclusion_reason']=='source_missing' for r in excluded)
    assert any('repeated header' in r['exclusion_reason'] for r in excluded)
    assert convert_behavior('10001','01',['trust'],behavior,bids,overwrite=True,curation_file=curation,runs=[1])==0
    assert (bids/ready[0]['events_path']).exists()
    assert not any((bids/r['events_path']).exists() for r in excluded)
    # Planning is stable across the successful write; rejected runs are untouched.
    assert cohort_run_plan(bids,behavior,set(),curation,['10001','10002'])==rows


def test_existing_canonical_bad_run_is_not_silently_excluded(tmp_path):
    from trust_analysis_handoff import cohort_run_plan
    bids,behavior,curation,raw=plan_fixture(tmp_path)
    event=bids/'sub-10001/ses-01/func/sub-10001_ses-01_task-trust_run-2_events.tsv'
    event.write_text('onset\tduration\n0\t1\n')
    with pytest.raises(ValueError,match='existing canonical events have unresolved source'):
        cohort_run_plan(bids,behavior,set(),curation,['10001'])
    assert event.read_text()=='onset\tduration\n0\t1\n'


def test_approved_short_run_remains_ready_and_source_exclusion_wins(tmp_path):
    from trust_analysis_handoff import cohort_run_plan
    bids,behavior,curation,raw=plan_fixture(tmp_path,short=True)
    converted=convert_source('trust',raw)
    with curation.open('a') as f:
        f.write(f'10001\t01\ttrust\t1\tunexpected_trial_count\t{converted.source_sha256}\t{converted.trial_fingerprint}\ttest-reviewer\tsynthetic approval\n')
    rows=cohort_run_plan(bids,behavior,set(),curation,['10001'])
    assert rows[0]['conversion_status']=='ready'
    excluded=cohort_run_plan(bids,behavior,{'10001'},curation,['10001'])
    assert all(r['exclusion_reason']=='source_excluded' for r in excluded)


def test_frozen_plan_rejects_source_changes(tmp_path,monkeypatch):
    from types import SimpleNamespace
    import trust_analysis_handoff as h
    bids,behavior,curation,raw=plan_fixture(tmp_path)
    root=tmp_path/'upstream';(root/'code').mkdir(parents=True)
    (root/'code/convert_behavior.py').write_text('# synthetic converter')
    (root/'code/behavior_curation.tsv').write_text(curation.read_text())
    work=tmp_path/'work';work.mkdir()
    a=SimpleNamespace(bids_root=bids,behavior_root=behavior,work=work)
    monkeypatch.setattr(h,'ROOT',root)
    before=h.checked_cohort_plan(a,set(),create=True)
    assert h.checked_cohort_plan(a,set())==before
    raw.write_text(raw.read_text()+'\n') # Same trials, changed source bytes.
    with pytest.raises(ValueError,match='sources/curation changed'):
        h.checked_cohort_plan(a,set())


def test_cohort_check_accepts_valid_runs_and_reports_unresolved(tmp_path,monkeypatch):
    import sys,json
    import trust_analysis_handoff as h
    from convert_behavior import convert_behavior
    from types import SimpleNamespace
    bids,behavior,curation,raw=plan_fixture(tmp_path)
    root=tmp_path/'upstream';(root/'code').mkdir(parents=True)
    (root/'code/convert_behavior.py').write_text('# synthetic converter')
    (root/'code/behavior_curation.tsv').write_text(curation.read_text())
    monkeypatch.setattr(h,'ROOT',root)
    # Include a real zero choice so the cohort schema gate exercises hidden feedback.
    import csv
    with raw.open() as f:rows=list(csv.DictReader(f))
    rows[0].update(resp='0',cLeft='0',highlow='low')
    write_delimited(raw,rows)
    assert convert_behavior('10001','01',['trust'],behavior,bids,overwrite=True,curation_file=curation,runs=[1])==0
    work=tmp_path/'work';work.mkdir();exclusions=tmp_path/'exclusions';exclusions.mkdir()
    event=next(bids.glob('sub-*/ses-01/func/*_run-1_events.tsv'))
    before=[{k:v for k,v in row.items() if k not in h.ADDED} for row in h.read(event)]
    snapshot=dict(subjects=['10001','10002'],events={str(event.relative_to(bids)):before},imaging=h.imaging_inventory(bids))
    (work/'cohort.json').write_text(json.dumps(snapshot))
    h.checked_cohort_plan(SimpleNamespace(bids_root=bids,behavior_root=behavior,work=work),set(),create=True)
    monkeypatch.setattr(sys,'argv',['handoff','check','--scope','cohort','--bids-root',str(bids),'--behavior-root',str(behavior),'--excluded-source-root',str(exclusions),'--work',str(work)])
    h.main()
    report=json.loads((work/'cohort_passed.json').read_text())
    assert report['status']=='passed' and report['runs']==1 and len(report['excluded_runs'])==2
    assert report['zero_choices']==1 and report['historical_columns_unchanged']



def test_behavior_batch_forwards_exact_run_selector(tmp_path):
    import os,subprocess
    from pathlib import Path
    import trust_analysis_handoff as h
    root=tmp_path/'project';code=root/'code';code.mkdir(parents=True)
    for name in ['run_convert_behavior.sh','pipeline_common.sh']:
        (code/name).write_text(Path(h.__file__).with_name(name).read_text())
    (code/'convert_behavior.py').write_text('# fake')
    (code/'behavior_curation.tsv').write_text('')
    sublist=tmp_path/'subjects';sublist.write_text('10001\n')
    behavior=tmp_path/'behavior';behavior.mkdir()
    excluded=tmp_path/'exclusions';excluded.mkdir()
    bin_dir=tmp_path/'bin';bin_dir.mkdir();calls=tmp_path/'calls'
    fake=bin_dir/'python3';fake.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$HANDOFF_CALLS"\ncase "$1" in */print_subjects.py) echo 10001;; esac\n');fake.chmod(0o755)
    env=dict(os.environ,PATH=str(bin_dir)+os.pathsep+os.environ['PATH'],HANDOFF_CALLS=str(calls),BEHAVIOR_ROOT=str(behavior),SOURCEDATA_EXCLUSIONS_ROOT=str(excluded))
    result=subprocess.run(['bash',str(code/'run_convert_behavior.sh'),'--sublist',str(sublist),'--sessions','01','--tasks','trust','--run','1','--jobs','1','--dry-run'],env=env,text=True,capture_output=True)
    assert result.returncode==0,result.stdout+result.stderr
    assert '--run 1' in calls.read_text() and '--subject 10001' in calls.read_text()

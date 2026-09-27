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

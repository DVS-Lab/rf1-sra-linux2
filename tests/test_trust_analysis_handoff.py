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

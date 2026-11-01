"""The VLQ class over a fake service: the lines before each request, a table note, the secrets, usage, the classes."""

import pytest
from fakes import lines_of, records_of
from fakes.vlq import PASSWORDS_SEEN, TOKEN, go, make_vlq

from qdevices import monitor
from qdevices.sites.base import SiteError


def test_each_line_is_on_disk_before_the_next_request(tmp_path):
    places, clock, fake, m, site = make_vlq(tmp_path)
    assert go(m, site, places, clock, max_order=1) == 0
    assert fake.last_line_at[("create", "backend_init")]["step"] == "init_submitting"
    assert fake.last_line_at[("create", "backend_run")]["event"] == "submitting"
    run_job = 102
    assert fake.last_line_at[("upload", run_job)]["step"] == "created"
    assert fake.last_line_at[("submit", run_job)]["step"] == "uploaded"
    result = next(e for e in lines_of(records_of(places)[0]) if e["event"] == "result")
    assert result["id"] == run_job and result["counts"] == {"1": 10} and result["seconds"] == 0.42
    assert result["published_seconds"] == 0.9


def test_a_table_note_of_the_init_done_line_is_printed_before_the_metered_job(tmp_path):
    places, clock, _fake, m, site = make_vlq(tmp_path)          # its iqm_target_attrs.pkl is not a pickle
    said = []
    assert go(m, site, places, clock, max_order=1, say=said.append) == 0
    done = next(e for e in lines_of(records_of(places)[0]) if e.get("step") == "init_done")
    assert done["table_note"].startswith("the table of the day was not read (the pickle cannot be read")
    line = f"  NOTE: order 1 (V1): {done['table_note']}"
    assert said.count(line) == 1 and said.index(line) < said.index("  job 102 sent")


def test_the_job_environment_and_the_envelope_password_never_reach_a_record(tmp_path):
    places, clock, _fake, m, site = make_vlq(tmp_path)
    go(m, site, places, clock, max_order=2)
    text = records_of(places)[0].read_text()
    assert "EnvironmentVariables" not in text and "Q_COMMAND" not in text
    for password in PASSWORDS_SEEN:
        assert password not in text and password[:8] not in text
    assert TOKEN[:8] not in text


def test_usage_counts_init_jobs_and_their_node_time(tmp_path):
    places, clock, _fake, m, site = make_vlq(tmp_path)
    go(m, site, places, clock, max_order=2)
    s = monitor.summary(records_of(places)[0])
    assert s.init_jobs == 2 and s.init_node_seconds == 40.0 and s.results == 2


@pytest.mark.parametrize("code, kind", [(400, "refused"), (422, "refused"), (401, "unknown"), (429, "unknown"),
                                        (500, "unknown")])
def test_the_classes_of_an_upload_answer(tmp_path, code, kind):
    _places, _clock, _fake, _m, site = make_vlq(tmp_path)
    error = SiteError("x", status=code, step="upload:circuit_0000.qasm")
    assert site.classify(error) == kind
    assert site.classify(SiteError("x", status=400, step="upload:user_token.enc")) == "unknown"

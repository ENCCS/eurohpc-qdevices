"""The record (sync, cut lines) and invariant 5 (the token filter)."""

import base64
import json
from types import SimpleNamespace

from fakes import TOKEN, FakeClock, FakeSite, lines_of, records_of, send, write_manifest
from test_call_paths import live

from qdevices import record
from qdevices.redact import HIDDEN, redact, redact_all

JWT = "eyJ" + "a" * 20 + "." + "b" * 30 + "." + "c" * 10
PASSWORD = "Q" * 50
B64 = base64.b64encode(PASSWORD.encode()).decode()


def test_a_cut_last_line_is_passed_over_and_the_next_line_starts_clean(tmp_path):
    path = tmp_path / "run_20260101T000000Z.jsonl"
    rec = record.Record(path, FakeClock(), {"site": "vlq"})
    rec.write("start", n=1)
    rec.close()
    with open(path, "a") as fh:
        fh.write('{"event": "submitted", "order": 1, "id": 12')       # a crash inside a write
    rec = record.Record(path, FakeClock(), {"site": "vlq"})
    rec.write("resume")
    rec.close()
    events, cut = record.RecordLines.read(path)
    assert [e["event"] for e in events] == ["start", "resume"]
    assert cut == [(2, '{"event": "submitted", "order": 1, "id": 12')]


def test_full_fsync_is_called_where_fcntl_has_it(tmp_path, monkeypatch):
    calls = []
    fake = SimpleNamespace(F_FULLFSYNC=51, fcntl=lambda fd, op: calls.append(op))
    monkeypatch.setattr(record, "fcntl", fake)
    rec = record.Record(tmp_path / "run_20260101T000000Z.jsonl", FakeClock(), {})
    rec.write("start")
    rec.close()
    assert calls == [51]


def test_the_patterns_need_no_state_of_the_process():
    text = (f"Bearer {JWT} and gAAAAABfernettext== and Z0FBQUFBbase64form= and "
            f"USER_JWT_PWD={B64} and 'USER_JWT_PWD': '{B64}' and "
            f'{{"Name": "USER_JWT_PWD", "Value": "{B64}"}} and '
            f'{{\\"Name\\": \\"USER_JWT_PWD\\", \\"Value\\": \\"{B64}\\"}}')
    out = redact(text)
    for secret in (JWT, "gAAAAABfernettext", "Z0FBQUFBbase64form", B64):
        assert secret not in out
    assert out.count(HIDDEN) >= 7


def test_the_secrets_of_this_process_go_whole_in_json_form_and_every_start_of_8():
    secret = 'abc"defgh\\ijklmnopqrstu'
    for text in (secret, json.dumps(secret), "body: " + secret[:12], "cut " + json.dumps(secret)[1:200][:10]):
        out = redact(text, [secret])
        assert secret[:8] not in out and json.dumps(secret)[1:9] not in out


def test_every_end_of_8_or_more_of_a_secret_goes_too():
    secret = 'abc"defgh\\ijklmnopqrstu'
    for k in range(8, len(secret)):
        for text in (secret[-k:] + " kept", "cut " + json.dumps(secret)[1:-1][-k:]):
            out = redact(text, [secret])
            assert secret[-8:] not in out and json.dumps(secret)[-9:-1] not in out, (k, text, out)
    assert redact("ghij" + secret[-7:], [secret]) == "ghij" + secret[-7:]       # an end of 7 is no secret


def test_a_cut_at_200_characters_leaves_no_part_of_a_secret():
    body = ("x" * 190) + TOKEN
    cut = body[:200]
    assert TOKEN[:8] not in redact(cut, [TOKEN])


def test_redact_all_keeps_the_form_of_a_line():
    line = {"a": [TOKEN, {"b": PASSWORD}], "n": 3}
    assert redact_all(line, [TOKEN, PASSWORD]) == {"a": [HIDDEN, {"b": HIDDEN}], "n": 3}


def test_no_secret_reaches_a_record_line_an_error_or_a_log(tmp_path, places, clock):
    body = f'{{"detail": "bad token {TOKEN}", "EnvironmentVariables": [{{"Name": "USER_JWT_PWD", "Value": "{B64}"}}],' \
           f' "jwt": "{JWT}"}}'
    site = FakeSite(submits={1: ("unknown", 500, body)})
    site._passwords = [PASSWORD, B64]
    site.secrets = lambda: [TOKEN, PASSWORD, B64]
    send(write_manifest(tmp_path / "m"), site, places, clock, max_order=1)
    text = records_of(places)[0].read_text()
    for secret in (TOKEN, TOKEN[:8], json.dumps(TOKEN)[1:-1], B64, B64[:8], PASSWORD[:8], JWT):
        assert secret not in text
    assert all(isinstance(line, dict) for line in lines_of(records_of(places)[0]))


def test_a_log_of_a_job_made_by_an_earlier_process_is_filtered(tmp_path, places, clock):
    from fakes import STATE

    m = write_manifest(tmp_path / "m")
    send(m, FakeSite(states={"J-1": [STATE()]}), places, clock, max_order=1)     # the wait time-out
    rec = records_of(places)[0]
    later = FakeSite(token="", states={"J-1": [STATE("FAILED", final=True)]})    # a new process knows no secret
    later.logs = lambda job_id: {"stderr.txt": f"auth {JWT} env USER_JWT_PWD={B64} enc gAAAAABxyzxyzxyz"}
    send(m, later, places, clock, resume=rec)
    text = rec.read_text()
    assert JWT not in text and B64 not in text and "gAAAAABxyz" not in text
    assert [line for line in lines_of(rec) if line["event"] == "failed"]


def test_a_job_id_that_holds_the_token_is_filtered_on_the_screen(tmp_path, places, clock):
    said = []
    site = FakeSite(submits={1: ("id", f"J-{TOKEN}")})
    assert live(write_manifest(tmp_path / "m"), site, places, clock, said.append, max_order=1) == 0
    assert "  job J-[hidden] sent" in said and not [line for line in said if TOKEN in line]
    assert ("result", f"J-{TOKEN}") in site.calls         # the site is asked with the id it gave

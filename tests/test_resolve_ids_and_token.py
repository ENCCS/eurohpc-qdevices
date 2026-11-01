"""Faults 29 and 31 of the plan: resolve refuses an empty job id or one no URL holds; a token expiry not finite."""

import base64

import httpx
import pytest
from fakes import FakeClock, FakeSite, lines_of, records_of, send, write_manifest
from fakes.vlq import VLQ_TEXT, FakeVLQ, creates, go

from qdevices import cli, runner
from qdevices.resolve import resolve
from qdevices.sites.vlq import VLQ, wire


def lost(tmp_path, places, clock):
    m = write_manifest(tmp_path / "m", jobs=(("J1", 10),))
    assert send(m, FakeSite(submits={1: ("noanswer",)}), places, clock, max_order=1) == 2
    return records_of(places)[0]


@pytest.mark.parametrize("job_id", ["", "u\n1", "u?1"], ids=["empty", "a newline", "a query"])
def test_resolve_job_refuses_an_empty_id_or_one_no_url_holds_and_writes_nothing(tmp_path, places, clock, job_id):
    rec = lost(tmp_path, places, clock)
    before = rec.read_bytes()
    with pytest.raises(runner.Refused) as refused:
        resolve(rec, 1, job_id, places=places, clock=clock, host="h")
    assert str(refused.value) == f"{rec}: --job {job_id!r} is empty or cannot be put in a URL as it is"
    assert rec.read_bytes() == before


def jwt(claim: bytes) -> str:
    """A synthetic JWT whose claims are these bytes."""
    return "eyJ" + "h" * 20 + "." + base64.urlsafe_b64encode(claim).decode().rstrip("=") + ".sig"


CLAIMS = {"infinity": b'{"exp": Infinity}', "nan": b'{"exp": NaN}', "1e400": b'{"exp": 1e400}'}


@pytest.mark.parametrize("case", list(CLAIMS))
def test_a_token_expiry_that_is_not_finite_cannot_be_read(case):
    assert wire.token_expiry(jwt(CLAIMS[case])) is None


@pytest.mark.parametrize("case", list(CLAIMS))
def test_check_vlq_says_that_the_expiry_of_such_a_token_cannot_be_read(capsys, places, case):
    clock = FakeClock()
    code = cli.main(["check", "vlq"], places=places, environ={"LEXIS_TOKEN": jwt(CLAIMS[case])},
                    make_site=lambda *a, **k: None, clock=clock, sleep=clock.sleep, host="h")
    assert code == 0 and "LEXIS token: its expiry cannot be read" in capsys.readouterr().out


@pytest.mark.parametrize("case", list(CLAIMS))
def test_a_vlq_send_with_such_a_token_stops_at_its_rule_before_any_job(tmp_path, places, clock, case):
    fake = FakeVLQ(places)
    site = VLQ(jwt(CLAIMS[case]), "VLQ", lexis_project="TEST-LEXIS", resource="R1", clock=clock, sleep=clock.sleep,
               wait_seconds=60, transport=httpx.MockTransport(fake))
    said: list[str] = []
    m = write_manifest(tmp_path / "m", site="vlq", jobs=(("V1", 10),), text=VLQ_TEXT)
    assert go(m, site, places, clock, say=lambda *a, **k: said.append(" ".join(map(str, a))), max_order=1) == 2
    stop = lines_of(records_of(places)[0])[-1]
    assert (stop["kind"], stop["rule"]) == ("rule", "token")
    assert stop["reason"] == "rule token: the time left on the token cannot be read"
    assert creates(fake) == [] and not [line for line in said if "A job may be at the site" in line]

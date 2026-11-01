"""`qdevices check` pinned whole, offline and with --live, and the read it stores, token filtered."""

import base64
import json

import pytest
from fakes import CONFIG, QASM, TOKEN, FakeClock, FakeSite, cfg, write_manifest
from fakes.eqe import Portal, manifest
from fakes.eqe import site as euroqexa_site
from fakes.vlq import STATUS_UP, creates, make_vlq
from fakes.vlq import TOKEN as LEXIS_TOKEN

from qdevices import check, cli, lock
from qdevices.sites.base import SiteError

PAIRS = [(0, 1), (1, 2), (2, 3), (3, 4), (0, 4)]
LIST = {"resources": {"M2": {"qubits": 9, "online": False}, "M1": {"qubits": 5, "online": True}}}
JWT = "eyJ" + "a" * 20 + "." + "b" * 30 + "." + "c" * 10           # synthetic, in the form of a JWT
PASSWORD = base64.b64encode(b"Q" * 50).decode()                    # synthetic, in the form of an envelope password


def lexis_token(seconds_left: float) -> str:
    """A synthetic LEXIS token: a JWT whose expiry claim is this long after the start of the fake clock."""
    claims = json.dumps({"exp": FakeClock().start.timestamp() + seconds_left}).encode()
    return "eyJ" + "h" * 20 + "." + base64.urlsafe_b64encode(claims).decode().rstrip("=") + ".sig"


class Recorded(FakeSite):
    """A fake site that adds each read and close to `steps`; its read raises `error` when one is given."""

    def __init__(self, steps: list, error: Exception | None = None, **kw) -> None:
        super().__init__(**kw)
        self.steps, self.error = steps, error

    def read(self) -> dict:
        self.steps.append("read")
        if self.error is not None:
            raise self.error
        return super().read()

    def close(self) -> None:
        self.steps.append("close")
        super().close()


def command(capsys, places, *args, environ=None, site=None) -> str:
    """`qdevices ARGS` with a fake clock; make_site gives `site`, or else a FakeSite of the site named."""
    clock, made = FakeClock(), []

    def make_site(man, name, token, **kw):
        made.append(name)
        return FakeSite(name) if site is None else site

    code = cli.main(list(args), places=places, environ=dict(environ or {}), make_site=make_site, clock=clock,
                    sleep=clock.sleep, host="host-a")
    out = capsys.readouterr()
    text = f"exit {code}\nmade {made}\n--- stdout\n{out.out}--- stderr\n{out.err}"
    stored = sorted(p for p in places.reads.rglob("*") if p.is_file()) if places.reads.exists() else []
    return text + "".join(f"--- stored {p.relative_to(places.reads).as_posix()}\n{p.read_text(encoding='utf-8')}"
                          for p in stored)


@pytest.mark.parametrize("case, site, environ", [
    ("token_set", "euroqexa", {"MQSS_TOKEN": TOKEN}),
    ("token_not_set", "euroqexa", {}),
    ("lexis_minutes", "vlq", {"LEXIS_TOKEN": lexis_token(7200)}),
    ("lexis_expired", "vlq", {"LEXIS_TOKEN": lexis_token(-90)}),
    ("not_a_jwt", "vlq", {"LEXIS_TOKEN": TOKEN}),
    ("piastq_no_key", "piastq", {}),
])
def test_check_offline_says_whether_the_token_is_set_and_never_prints_it(capsys, places, golden, case, site,
                                                                          environ):
    places.config.write_text(CONFIG)
    text = command(capsys, places, "check", site, environ=environ)
    golden(f"check_offline_{case}", text)
    assert all(token not in text for token in environ.values())


@pytest.mark.parametrize("case, window", [("window_outside", "Mon 09:00-12:00"), ("window_inside", "Mon 12:00-14:00")])
def test_check_offline_says_whether_the_fake_clock_is_inside_the_piastq_window(capsys, places, golden, case, window):
    zone = f'[piastq]\nwindow = ["{window}"]\nwindow_zone = "Europe/Warsaw"\n'     # 12:00 UTC is 13:00 there
    places.config.write_text(CONFIG.replace("[piastq]\n", zone))
    golden(f"check_offline_{case}", command(capsys, places, "check", "piastq", environ={"PCSS_API_KEY": TOKEN}))


def test_check_live_prints_and_stores_a_euroqexa_read_with_its_layout_and_the_pin(capsys, places, golden, tmp_path):
    places.config.write_text(CONFIG)
    seen, m = [], manifest(tmp_path / "m", QASM)
    golden("check_live_euroqexa", command(capsys, places, "check", "euroqexa", "--live", "--manifest", str(m),
                                          environ={"MQSS_TOKEN": TOKEN}, site=euroqexa_site(Portal(5, PAIRS, seen))))
    assert {method for method, _ in seen} == {"GET"}                   # reads only: no job of any kind


def test_check_live_with_no_manifest_stores_a_list_of_the_machines(capsys, places, golden):
    places.config.write_text(CONFIG)
    golden("check_live_list", command(capsys, places, "check", "euroqexa", "--live", environ={"MQSS_TOKEN": TOKEN},
                                      site=FakeSite(read=LIST)))


def test_check_live_prints_and_stores_a_vlq_read_with_its_status(capsys, golden, tmp_path):
    places, _clock, fake, m, vlq = make_vlq(tmp_path, status_file={**STATUS_UP, "QPU_status": False})
    places.config.write_text(CONFIG)
    golden("check_live_vlq", command(capsys, places, "check", "vlq", "--live", "--manifest", str(m),
                                     environ={"LEXIS_TOKEN": LEXIS_TOKEN}, site=vlq))
    assert creates(fake) == []


def test_check_live_that_cannot_read_the_machine_fails_with_the_token_filtered(capsys, places, golden):
    places.config.write_text(CONFIG)
    error = SiteError(f"HTTP 401 to GET resources/M1: the token {TOKEN} or {JWT} is not valid", status=401,
                      step="read")
    text = command(capsys, places, "check", "euroqexa", "--live", environ={"MQSS_TOKEN": TOKEN},
                   site=Recorded([], error))
    golden("check_live_failed", text)
    assert TOKEN not in text and JWT not in text and not places.reads.exists()


def test_the_read_on_the_screen_hides_the_token_and_a_jwt(capsys, places):
    places.config.write_text(CONFIG)
    read = {"machine": f"M1 {TOKEN}", "online": True, "qubits": 5,
            "resources": {f"R {JWT}": {"qubits": TOKEN, "online": JWT}}}
    text = command(capsys, places, "check", "euroqexa", "--live", environ={"MQSS_TOKEN": TOKEN},
                   site=FakeSite(read=read))
    shown = text.split("--- stored")[0]
    assert "  machine: M1 [hidden]" in shown and "  R [hidden]: [hidden] qubits, online [hidden]" in shown
    assert TOKEN not in shown and JWT not in shown


def test_the_stored_read_hides_the_token_a_jwt_and_an_envelope_password(capsys, places, golden):
    places.config.write_text(CONFIG)
    read = {"machine": "M1", "online": True, "qubits": 5, "detail": f"Bearer {TOKEN}", "refresh": JWT,
            "env": [{"Name": "USER_JWT_PWD", "Value": PASSWORD}]}
    golden("check_live_secrets", command(capsys, places, "check", "euroqexa", "--live", environ={"MQSS_TOKEN": TOKEN},
                                         site=FakeSite(read=read)))
    stored = next((places.reads / "euroqexa").glob("read_*.json")).read_text(encoding="utf-8")
    assert TOKEN not in stored and JWT not in stored and PASSWORD not in stored
    assert stored.count("[hidden]") == 3


@pytest.mark.parametrize("case, args, environ", [
    ("no_token", ("check", "euroqexa", "--live"), {}),
    ("vlq_no_manifest", ("check", "vlq", "--live"), {"LEXIS_TOKEN": LEXIS_TOKEN}),
    ("other_site", ("check", "vlq", "--live", "--manifest", "MANIFEST"), {"LEXIS_TOKEN": LEXIS_TOKEN}),
])
def test_check_live_is_refused_before_the_lock(capsys, places, golden, tmp_path, case, args, environ):
    places.config.write_text(CONFIG)
    m = write_manifest(tmp_path / "m")
    golden(f"check_refused_{case}", command(capsys, places, *(str(m) if a == "MANIFEST" else a for a in args),
                                            environ=environ))
    assert not places.state.exists() and not places.reads.exists()


def test_check_live_while_the_lock_is_held_is_refused_before_a_site_is_made(capsys, places, golden):
    places.config.write_text(CONFIG)
    release = lock.Locks(places.state, host="host-a").take("euroqexa")
    try:
        text = command(capsys, places, "check", "euroqexa", "--live", environ={"MQSS_TOKEN": TOKEN})
    finally:
        release()
    golden("check_refused_lock", text)


@pytest.mark.parametrize("error, code", [(None, 0), (SiteError("HTTP 503 to GET resources/M1", status=503,
                                                               step="read"), 1)])
def test_check_live_takes_the_lock_first_and_releases_it_last(places, clock, error, code):
    steps = []

    def take(name):
        steps.append(f"lock {name}")
        return lambda: steps.append("release")

    def make_site(man, name, token, **kw):
        steps.append("make_site")
        return Recorded(steps, error)

    assert check.check("euroqexa", live=True, token=TOKEN, manifest_path=None, cfg=cfg(), places=places, clock=clock,
                       sleep=clock.sleep, host="host-a", make_site=make_site, take_lock=take,
                       say=lambda *a, **k: None) == code
    assert steps == ["lock euroqexa", "make_site", "read", "close", "release"]

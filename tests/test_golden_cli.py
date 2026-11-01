"""The command line pinned whole: help, argparse errors, --version, login texts and REFUSED lines."""

import pytest
from fakes import CONFIG, TOKEN, FakeClock, FakeSite, records_of, send, write_manifest

from qdevices import cli, lock
from qdevices.sites import SITES

COMMANDS = ("check", "dry-run", "send", "resolve", "unlock", "runs", "usage", "jobs", "login")
LIVE = ("--live", "--max-order", "1")
WITH_TOKEN = {"MQSS_TOKEN": TOKEN}


@pytest.fixture(autouse=True)
def columns(monkeypatch):
    """argparse wraps its help and usage lines at the width of the terminal."""
    monkeypatch.setenv("COLUMNS", "100")


@pytest.fixture
def configured(places):
    """The places of the test, with the config of the tests in qdevices.toml."""
    places.config.write_text(CONFIG)
    return places


def command(capsys, places, *args, environ=None, made=None) -> str:
    """`qdevices ARGS` with a fake clock and fake sites, each added to `made`: exit code, stdout and stderr."""
    clock, sites = FakeClock(), [] if made is None else made

    def make_site(man, name, token, **kw):
        sites.append(FakeSite(name))
        return sites[-1]

    code = cli.main(list(args), places=places, environ=dict(environ or {}), make_site=make_site, clock=clock,
                    sleep=clock.sleep, host="host-a")
    out = capsys.readouterr()
    return f"exit {code}\n--- stdout\n{out.out}--- stderr\n{out.err}"


def test_the_help_of_the_app(capsys, configured, golden):
    golden("cli_help", command(capsys, configured, "--help"))


@pytest.mark.parametrize("name", COMMANDS)
def test_the_help_of_each_command(capsys, configured, golden, name):
    golden(f"cli_help_{name.replace('-', '_')}", command(capsys, configured, name, "--help"))


def test_the_bare_command_prints_the_help_and_sends_nothing(capsys, configured, golden):
    made = []
    golden("cli_bare", command(capsys, configured, made=made))
    assert made == [] and not configured.records.exists()


def test_a_wrong_argument_is_an_argparse_error_with_exit_code_1(capsys, configured, golden):
    golden("cli_argparse_error", command(capsys, configured, "send", "m.json", "--max-order", "x"))


def test_a_command_the_app_does_not_have_is_an_argparse_error(capsys, configured, golden):
    golden("cli_unknown_command", command(capsys, configured, "cancel"))


def test_the_version(capsys, configured, golden):
    golden("cli_version", command(capsys, configured, "--version"))


@pytest.mark.parametrize("site", list(SITES))
def test_the_login_text_of_each_site(capsys, configured, golden, site):
    golden(f"cli_login_{site}", command(capsys, configured, "login", site))


def test_a_send_without_live_prints_the_line_that_nothing_is_sent(capsys, configured, golden, tmp_path):
    made = []
    m = write_manifest(tmp_path / "m")
    golden("cli_send_nothing", command(capsys, configured, "send", str(m), "--max-order", "1", environ=WITH_TOKEN,
                                       made=made))
    assert made == [] and not configured.records.exists()


def test_a_send_with_a_manifest_that_fails_is_refused(capsys, configured, golden, tmp_path):
    made = []
    m = write_manifest(tmp_path / "m", format="qdevices/0", project="")
    golden("cli_refused_manifest", command(capsys, configured, "send", str(m), *LIVE, environ=WITH_TOKEN, made=made))
    assert made == [] and not configured.records.exists()


def test_a_send_with_a_rules_file_that_raises_on_import_is_refused(capsys, configured, golden, tmp_path):
    made, rules = [], tmp_path / "rules.py"
    rules.write_text("raise ValueError('the limits of this experiment are not set')\n")
    m = write_manifest(tmp_path / "m")
    golden("cli_refused_rules_file", command(capsys, configured, "send", str(m), *LIVE, "--rules", str(rules),
                                             environ=WITH_TOKEN, made=made))
    assert made == [] and not configured.records.exists()


def test_a_config_that_is_not_toml_is_refused(capsys, places, golden):
    places.config.write_text("[euroqexa\nprojects = 1\n")
    golden("cli_refused_config", command(capsys, places, "runs"))


def test_check_live_with_a_manifest_that_fails_is_refused_before_the_lock(capsys, configured, golden, tmp_path):
    made = []
    m = write_manifest(tmp_path / "m", format="qdevices/0")
    golden("cli_refused_check_manifest", command(capsys, configured, "check", "euroqexa", "--live", "--manifest",
                                                 str(m), environ=WITH_TOKEN, made=made))
    assert made == [] and not configured.state.exists() and not configured.reads.exists()


def test_a_send_while_the_lock_is_held_is_refused(capsys, configured, golden, tmp_path):
    made = []
    m = write_manifest(tmp_path / "m")
    release = lock.Locks(configured.state, host="host-a").take("euroqexa")
    try:
        text = command(capsys, configured, "send", str(m), *LIVE, environ=WITH_TOKEN, made=made)
    finally:
        release()
    golden("cli_refused_lock", text)
    assert [site.calls for site in made] == [[]] and not configured.records.exists()


def test_a_send_while_an_order_of_the_site_is_lost_is_refused_and_changes_nothing(capsys, configured, golden,
                                                                                 tmp_path):
    made, m = [], write_manifest(tmp_path / "m")
    assert send(m, FakeSite(submits={1: ("noanswer",)}), configured, FakeClock(), max_order=1) == 2   # 1 is lost
    rec = records_of(configured)[0]
    before = rec.read_bytes()
    capsys.readouterr()
    golden("cli_refused_lost_order", command(capsys, configured, "send", str(m), *LIVE, environ=WITH_TOKEN, made=made))
    assert [site.calls for site in made] == [[]] and rec.read_bytes() == before


def test_resolve_with_no_decision_flag_is_refused_and_changes_nothing(capsys, configured, golden, tmp_path):
    m = write_manifest(tmp_path / "m")
    assert command(capsys, configured, "send", str(m), *LIVE, environ=WITH_TOKEN).startswith("exit 0\n")
    rec = records_of(configured)[0]
    before = rec.read_bytes()
    golden("cli_resolve_no_flag", command(capsys, configured, "resolve", str(rec), "1"))
    assert rec.read_bytes() == before and not list(configured.records.rglob("older_decisions.jsonl"))

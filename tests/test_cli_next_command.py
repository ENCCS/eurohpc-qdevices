"""The commands the app prints for the next step: given back to the command line, they are accepted."""

import json
import shlex

from fakes import CONFIG, TOKEN, FakeClock, FakeSite, events, places_in, records_of, write_manifest

from qdevices import cli
from qdevices.sites.base import Expired


def command(places, *args, site=None, clock=None) -> int:
    """`qdevices ARGS` with the token set, a fake clock and a fake site."""
    clock = clock or FakeClock()
    return cli.main(list(args), places=places, environ={"MQSS_TOKEN": TOKEN}, clock=clock, sleep=clock.sleep,
                    make_site=lambda man, name, token, **kw: FakeSite(name) if site is None else site, host="host-a")


def printed(capsys, lead: str) -> list[str]:
    """The words of the last command the app printed after `lead`, without `qdevices`."""
    row = [r for r in capsys.readouterr().out.splitlines() if lead in r][-1]
    words = shlex.split(row.split(lead, 1)[1])
    assert words[0] == "qdevices"
    return words[1:]


def spaced(tmp_path):
    """A manifest and the places of the app in a folder with a space: the printed commands quote each path."""
    folder = tmp_path / "a folder"
    m, places = write_manifest(folder / "m"), places_in(folder)
    places.config.write_text(CONFIG)
    return m, places


def test_the_commands_a_call_prints_give_its_rules_file_and_are_accepted(tmp_path, capsys):
    folder = tmp_path / "a folder"                  # a space in each path: the printed commands quote them
    m, path, places = write_manifest(folder / "m"), folder / "my rules.py", places_in(folder)
    places.config.write_text(CONFIG)
    path.write_text("# the rules of an experiment\n")

    def hit():
        raise KeyboardInterrupt()

    stopped = FakeSite(states={"J-1": [hit]})
    assert command(places, "send", str(m), "--live", "--max-order", "1", "--rules", str(path), site=stopped) == 130
    collect = printed(capsys, "Collect with: ")
    assert collect[1:2] == [str(m)] and collect[-2:] == ["--rules", str(path.resolve())]
    assert command(places, *collect) == 0                                  # collects order 1
    go_on = printed(capsys, "Go on with: ")
    go_on[go_on.index("N")] = "2"
    assert command(places, *go_on) == 0                                    # sends order 2
    rec = records_of(places)[0]
    assert [e["order"] for e in events(rec, "result")] == [1, 2]
    assert [e.get("rules_note") for e in events(rec, "resume")] == [None, None]


def test_the_over_limit_command_of_the_rule_job_time_is_accepted(tmp_path, capsys):
    m, places = spaced(tmp_path)
    waited = FakeSite()
    waited.result = lambda job_id: {"counts": {"1": 10}, "seconds": 500.0}       # above job_seconds_limit, 100 s
    assert command(places, "send", str(m), "--live", "--max-order", "1", site=waited) == 2
    assert command(places, *printed(capsys, "record your decision with: ")) == 0
    assert events(records_of(places)[0], "resolved")[-1]["over_limit"] is True


def test_the_expired_command_of_a_result_the_site_no_longer_gives_is_accepted(tmp_path, capsys):
    m, places = spaced(tmp_path)
    gone, later = FakeSite(states={"J-1": [Expired("the site does not know the job", step="status")]}), FakeClock()
    later.t = 11 * 60                                                       # the second call, 11 minutes on
    assert command(places, "send", str(m), "--live", "--max-order", "1", site=gone) == 1
    assert command(places, "send", str(m), "--live", "--resume", str(records_of(places)[0]), site=gone,
                   clock=later) == 1
    assert command(places, *printed(capsys, "record it with: "), clock=later) == 0
    assert events(records_of(places)[0], "resolved")[-1]["expired"] is True


def test_the_check_command_of_the_dry_run_for_an_old_read_is_accepted(tmp_path, capsys):
    m, places = spaced(tmp_path)
    (places.reads / "euroqexa").mkdir(parents=True)
    old = {"read_at": "2026-01-01T12:00:00+00:00", "machine": "M1", "qubits": 5}      # older than 24 hours
    (places.reads / "euroqexa" / "read_20260101T120000Z.json").write_text(json.dumps(old))
    assert command(places, "dry-run", str(m)) == 0
    assert command(places, *printed(capsys, "read it again with ")) == 0
    assert len(list((places.reads / "euroqexa").glob("read_*.json"))) == 2

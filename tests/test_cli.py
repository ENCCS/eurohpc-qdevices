"""A live call needs an explicit flag; exit codes from the command line; the token variable."""

import pytest
from fakes import CONFIG, TOKEN, FakeClock, FakeSite, places_in, records_of, write_manifest

from qdevices import cli


def setup(tmp_path):
    places = places_in(tmp_path)
    places.config.write_text(CONFIG)
    made = []

    def make_site(man, name, token, **kw):
        site = FakeSite(name)
        made.append((site, token))
        return site

    return places, made, make_site


def main(args, places, make_site, environ=None):
    clock = FakeClock()
    return cli.main(args, places=places, environ={} if environ is None else environ, make_site=make_site,
                    clock=clock, sleep=clock.sleep, host="host-a")


def test_the_bare_command_sends_nothing(tmp_path, capsys):
    places, made, make_site = setup(tmp_path)
    assert main([], places, make_site) == 1
    assert made == [] and not places.records.exists()


@pytest.mark.parametrize("extra", [[], ["--max-order", "1"], ["--resume", "x.jsonl"], ["--live"]])
def test_send_without_live_and_a_stage_sends_nothing(tmp_path, extra):
    places, made, make_site = setup(tmp_path)
    m = write_manifest(tmp_path / "m")
    assert main(["send", str(m), *extra], places, make_site, {"MQSS_TOKEN": TOKEN}) == 1
    assert made == [] and not places.records.exists()


def test_a_wrong_argument_is_exit_code_1(tmp_path):
    places, _made, make_site = setup(tmp_path)
    assert main(["send"], places, make_site) == 1
    assert main(["send", "m.json", "--max-order", "x"], places, make_site) == 1


def test_a_live_send_reads_the_token_once_and_deletes_it_before_the_rules_file(tmp_path, monkeypatch):
    places, made, make_site = setup(tmp_path)
    monkeypatch.setenv("MQSS_TOKEN", TOKEN)
    rules = tmp_path / "rules.py"
    seen = tmp_path / "seen.txt"
    rules.write_text(f"import os\nopen({str(seen)!r}, 'w').write(repr(os.environ.get('MQSS_TOKEN')))\n")
    m = write_manifest(tmp_path / "m")
    clock = FakeClock()
    code = cli.main(["send", str(m), "--live", "--max-order", "1", "--rules", str(rules)], places=places,
                    make_site=make_site, clock=clock, sleep=clock.sleep, host="host-a")
    assert code == 0
    assert seen.read_text() == "None"
    assert made[0][1] == TOKEN
    import os
    assert "MQSS_TOKEN" not in os.environ


def test_no_token_is_refused(tmp_path):
    places, made, make_site = setup(tmp_path)
    m = write_manifest(tmp_path / "m")
    assert main(["send", str(m), "--live", "--max-order", "1"], places, make_site) == 1
    assert made == []


def test_exit_codes_0_and_2_from_a_scripted_run(tmp_path):
    places, _made, make_site = setup(tmp_path)
    m = write_manifest(tmp_path / "m")
    assert main(["send", str(m), "--live", "--max-order", "1"], places, make_site, {"MQSS_TOKEN": TOKEN}) == 0

    def refusing(man, name, token, **kw):
        return FakeSite(name, submits={2: ("refuse", 400)})

    rec = records_of(places)[0]
    assert main(["send", str(m), "--live", "--resume", str(rec), "--max-order", "2"], places, refusing,
                {"MQSS_TOKEN": TOKEN}) == 2


def test_no_flag_names_an_address_or_a_folder(capsys):
    for command in ("send", "check", "dry-run", "resolve", "unlock", "runs", "usage"):
        with pytest.raises(SystemExit):
            cli.parser().parse_args([command, "--help"])
        text = capsys.readouterr().out.lower()
        for word in ("--url", "--address", "--records", "--lock", "--host-url", "--endpoint"):
            assert word not in text


def test_check_offline_says_if_the_token_is_set_and_never_prints_it(tmp_path, capsys):
    places, made, make_site = setup(tmp_path)
    assert main(["check", "euroqexa"], places, make_site, {"MQSS_TOKEN": TOKEN}) == 0
    out = capsys.readouterr().out
    assert "MQSS_TOKEN: set" in out and TOKEN not in out and made == []
    assert main(["check", "piastq"], places, make_site) == 1


def test_check_live_stores_one_read_and_makes_no_job(tmp_path):
    places, made, make_site = setup(tmp_path)
    assert main(["check", "euroqexa", "--live"], places, make_site, {"MQSS_TOKEN": TOKEN}) == 0
    site = made[0][0]
    assert site.calls == [("read",)]
    assert len(list((places.reads / "euroqexa").glob("read_*.json"))) == 1


@pytest.mark.parametrize("site, variable", [("euroqexa", "MQSS_TOKEN"), ("vlq", "LEXIS_TOKEN"),
                                            ("piastq", "PCSS_API_KEY")])
def test_login_prints_the_way_to_a_token_and_the_variable(tmp_path, capsys, site, variable):
    places, made, make_site = setup(tmp_path)
    assert main(["login", site], places, make_site) == 0
    out = capsys.readouterr().out
    assert variable in out and made == []
    for unsourced in ("device flow", "six hours", "capabilities", "with the allocation"):   # no public page says so
        assert unsourced not in out


def test_runs_jobs_and_usage_read_records(tmp_path, capsys):
    places, _made, make_site = setup(tmp_path)
    m = write_manifest(tmp_path / "m")
    main(["send", str(m), "--live", "--max-order", "2"], places, make_site, {"MQSS_TOKEN": TOKEN})
    capsys.readouterr()
    assert main(["runs"], places, make_site) == 0
    assert "2 results of 3 jobs" in capsys.readouterr().out
    assert main(["jobs", str(records_of(places)[0])], places, make_site) == 0
    assert "J-1" in capsys.readouterr().out
    assert main(["usage"], places, make_site) == 0
    assert "TEST-PROJECT" in capsys.readouterr().out


def test_dry_run_passes_offline(tmp_path, capsys):
    places, made, make_site = setup(tmp_path)
    m = write_manifest(tmp_path / "m")
    assert main(["dry-run", str(m)], places, make_site) == 0
    assert "Dry run passed" in capsys.readouterr().out and made == []


def test_dry_run_notes_a_config_shot_limit_above_the_site_limit(tmp_path, capsys):
    places, made, make_site = setup(tmp_path)
    m = write_manifest(tmp_path / "m", site="piastq", jobs=(("J1", 100),),
                       text=b'{"number_of_qubits": 1, "quantum_circuit": [{"operation": "MEASURE"}]}')
    assert main(["dry-run", str(m)], places, make_site) == 0
    assert "note      site_max_shots" not in capsys.readouterr().out
    places.config.write_text(CONFIG.replace("[piastq]\n", "[piastq]\nsite_max_shots = 400\n"))
    assert main(["dry-run", str(m)], places, make_site) == 0
    out = capsys.readouterr().out
    assert "site_max_shots 400 is above the limit of 200 the app holds for piastq" in out
    assert "Dry run passed" in out and made == []


def test_check_live_with_no_machine_lists_the_resources(tmp_path, capsys):
    places, _made, make_site = setup(tmp_path)

    def listing(man, name, token, **kw):
        site = make_site(man, name, token, **kw)
        site._read = {"resources": {"EQE1": {"qubits": 52, "online": True}, "Q5": {"qubits": 5, "online": False}}}
        return site

    assert main(["check", "euroqexa", "--live"], places, listing, {"MQSS_TOKEN": TOKEN}) == 0
    out = capsys.readouterr().out
    assert "EQE1: 52 qubits, online True" in out and "Q5: 5 qubits, online False" in out

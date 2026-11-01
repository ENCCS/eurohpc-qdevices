"""examples/qrisp/send_all.sh, offline: a stand-in `qdevices` logs each call, runs the dry run and opens no socket."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
SCRIPT = EXAMPLES / "qrisp" / "send_all.sh"
STAND_IN = """#!{python}
import os, socket, sys
from pathlib import Path

def _no_network(*args, **kwargs):
    raise OSError("a network call")

socket.socket.connect = socket.socket.connect_ex = socket.getaddrinfo = _no_network
with open({log!r}, "a", encoding="utf-8") as log:
    log.write(" ".join(sys.argv[1:]) + "\\n")
if sys.argv[1] != "dry-run":
    sys.exit(int(os.environ.get("FAIL_" + Path(sys.argv[2]).parent.name, 0)) if sys.argv[1] == "send" else 0)
from qdevices import config, dryrun
from qdevices.paths import Places

tmp = Path({tmp!r})
places = Places(records=tmp / "records", reads=tmp / "reads", state=tmp / "state", config=tmp / "qdevices.toml")
sys.exit(dryrun.dry_run(Path(sys.argv[2]), cfg=config.load(Path({toml!r})), places=places))
"""


def run(tmp_path, *args, **env):
    """Run the script, the stand-in first on PATH and no MQSS_TOKEN: the exit code, the output and the calls."""
    bin_dir, log = tmp_path / "bin", tmp_path / "calls.log"
    bin_dir.mkdir(exist_ok=True)
    (bin_dir / "qdevices").write_text(STAND_IN.format(python=sys.executable, log=str(log), tmp=str(tmp_path),
                                                      toml=str(EXAMPLES / "qdevices.toml")), encoding="utf-8")
    (bin_dir / "qdevices").chmod(0o755)
    base = {k: v for k, v in os.environ.items() if k != "MQSS_TOKEN"}
    done = subprocess.run(["bash", SCRIPT, *args], capture_output=True, text=True, check=False,
                          env=base | {"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"} | env)
    calls = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    return done.returncode, done.stdout + done.stderr, calls


def own_copy(tmp_path, project="EXAMPLE-PROJECT"):
    """A copy of the examples with a project of one's own, as qrisp-examples --project writes it."""
    copy = tmp_path / "my-runs"
    shutil.copytree(EXAMPLES / "qrisp", copy, ignore=shutil.ignore_patterns("*.py", "*.sh", "__pycache__"))
    for manifest in copy.glob("*/manifest.json"):
        manifest.write_text(manifest.read_text(encoding="utf-8").replace("MY-PROJECT", project), encoding="utf-8")
    return copy


def sizes(folder):
    return sorted(folder.glob("*/manifest.json"), key=lambda m: sum(f.stat().st_size for f in m.parent.glob("*.qasm")))


def test_without_a_flag_it_only_dry_runs_each_manifest_smallest_first(tmp_path):
    code, out, calls = run(tmp_path)
    assert code == 0, out
    assert calls == [f"dry-run {m}" for m in sizes(SCRIPT.parent)]
    assert out.count("Dry run passed. Nothing was sent.") == len(calls) == 11
    assert "would send: qdevices send" in out


def test_live_refuses_the_placeholder_project_before_any_call(tmp_path):
    code, out, calls = run(tmp_path, "--live", "qft3", MQSS_TOKEN="not-a-token")
    assert (code, calls) == (2, [])
    assert "pixi run --manifest-path examples/qrisp/pixi.toml qrisp-examples --project YOURS --out my-runs" in out


def test_live_needs_the_token_in_the_environment(tmp_path):
    code, out, calls = run(tmp_path, "--live", "--dir", own_copy(tmp_path))
    assert (code, calls) == (2, [])
    assert "MQSS_TOKEN" in out


@pytest.mark.parametrize("names", [(), ("qubo", "qft3")], ids=["all", "two"])
def test_live_checks_once_then_sends_each_once_and_stops_at_a_failure(tmp_path, names):
    copy = own_copy(tmp_path)
    chosen = [m for m in sizes(copy) if not names or m.parent.name in names]
    stop = chosen[-2].parent.name
    code, out, calls = run(tmp_path, "--live", "--dir", str(copy), *names, MQSS_TOKEN="x", **{f"FAIL_{stop}": "4"})
    assert code == 4
    assert calls[0] == f"check euroqexa --live --manifest {chosen[0]}"
    assert calls[1:] == [f"send {m} --live --max-order 1" for m in chosen[:-1]]
    assert f"Stopped at {stop} (exit 4)" in out and f"--live --dir {copy} {chosen[-1].parent.name}\n" in out


def test_each_folder_has_the_same_run_script_and_it_is_executable():
    model = EXAMPLES / "qrisp" / "run_one.sh"
    folders = [m.parent for m in (EXAMPLES / "qrisp").glob("*/manifest.json")]
    assert len(folders) == 11
    for folder in folders:
        script = folder / "run.sh"
        assert script.read_bytes() == model.read_bytes() and os.access(script, os.X_OK)


@pytest.mark.parametrize(("args", "code", "said"), [(["--live"], 2, "MY-PROJECT"), (["--other"], 2, "usage")])
def test_a_run_script_refuses_before_any_call(args, code, said):
    done = subprocess.run(["bash", str(EXAMPLES / "qrisp" / "ising" / "run.sh"), *args], capture_output=True, text=True,
                          env={"PATH": "/usr/bin:/bin"})
    assert done.returncode == code and said in done.stderr

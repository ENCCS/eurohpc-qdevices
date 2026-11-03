"""The README.md of an example folder: what it does, a diagram, what came back, how to run it."""

from dataclasses import dataclass
from typing import Final

MANUAL: Final = "https://enccs.github.io/eurohpc-qdevices/"
BINDER: Final = "https://mybinder.org/v2/gh/ENCCS/eurohpc-qdevices/main?urlpath=doc/tree/examples/all_examples.ipynb"
NOT_SENT: Final = "Not sent yet with this app."
DRAWN: Final = {"hamiltonian/state_transfer": "MAIN", "euroqexa-three-jobs": "BELL"}   # circuit.png; else the first job
ONE_RUN: Final = "One run, on one day: it shows how much of the answer survived that day, not how good the machine is."
FILES: Final = (
    "| `manifest.json` | what to send: the site, your project, and for each job its file, its SHA-256 and its shots |\n"
    "| `emulate.sh` | emulates the example; nothing is sent |\n"
    "| `qrisp_emulated.json` | the share of each key on Qrisp's emulator, stored, so `./emulate.sh` needs no Qrisp |\n"
    "| `qutip_emulated.json` | the share of each key on QuTiP, with no noise, stored, so `./emulate.sh` needs no "
    "QuTiP |\n"
    "| `circuit.png` | the picture of the circuit above, drawn by qutip-qip |\n"
    "| `outcomes.png` | the chart of the outcomes above; from the top of the clone, `pixi run --manifest-path "
    "examples/qrisp/pixi.toml pictures` draws both again |\n"
    "| `run.sh` | checks the example offline for a real send; also `--login` and `--counts` |\n"
    "| `submit.sh` | sends the example to the machine |\n")


@dataclass(frozen=True, slots=True)
class Site:
    """What a README says of a machine: its name, token, the form of its files, what it does with them, the names."""

    title: str
    page: str
    token: str
    form: str
    runs: str
    names: str


SITES: Final = {
    "euroqexa": Site("Euro-Q-Exa", "euroqexa", "MQSS_TOKEN", "the circuit in OpenQASM 2; the site compiles it",
                     "The site compiles the text and runs the shots", "`MY-PROJECT`"),
    "vlq": Site("VLQ", "vlq", "LEXIS_TOKEN", "the circuit in OpenQASM 3, in the machine's own gates; the site does not "
                "compile it", "The machine runs the text as written", "`MY-PROJECT`, `MY-LEXIS-PROJECT` and "
                "`MY-VLQ-RESOURCE`"),
    "piastq": Site("Piast-Q", "piastq", "PCSS_API_KEY", "the circuit as the broker's list of operations",
                   "The broker passes it on and the machine runs the shots", "`MY-PROJECT`"),
}


def flow(steps: tuple[str, ...]) -> str:
    """A simple block diagram of some steps, which GitHub draws from this text; a long one runs downwards."""
    nodes = " --> ".join(f's{i}["{step}"]' for i, step in enumerate(steps))
    return f"```mermaid\nflowchart {'TD' if len(steps) > 6 else 'LR'}\n    {nodes}\n```\n"


def _browser(path: str, notebook: str) -> str:
    badge = "Or in your browser, with nothing to install: [![Run on Binder](https://mybinder.org/badge_logo.svg)]"
    if not notebook:
        return (f"{badge}({BINDER}). The first start can take some minutes. That page holds all the examples: put "
                f"`{path}` in `NAME` under Choose one.\n")
    return (f"{badge}({notebook}), the notebook of this folder. The first start can take some minutes. "
            f"[`all_examples.ipynb`]({'../' * (path.count('/') + 1)}all_examples.ipynb) holds all the examples: put "
            f"`{path}` in `NAME` under Choose one.\n")


def _emulate(path: str, notebook: str = "") -> str:
    return (
        f"## Emulate it\n\nYour computer computes what the machine would do: no account, no token, and nothing is "
        f"sent. On your own computer:\n\n```bash\n"
        f"git clone --depth 1 https://github.com/ENCCS/eurohpc-qdevices\ncd eurohpc-qdevices/examples/{path}\n"
        f"./emulate.sh\n```\n\nIt prints what a perfect machine gives, then the stored results of Qrisp's emulator "
        f"and of QuTiP, with no noise, then what the machine gave if this example has run. Add a simple model of "
        f"noise, which is ours and not a model of any machine, with `./emulate.sh --noise 0.03 "
        f"--readout 0.03`. It needs Python 3.8 or later, or [pixi](https://pixi.sh).\n\n{_browser(path, notebook)}")


@dataclass(frozen=True, slots=True)
class Readme:
    """The page of one folder: `back` is what came back from the machine, or "" for a job not sent yet."""

    site: str
    title: str
    about: str
    steps: tuple[str, ...]
    perfect: str
    back: str
    files: tuple[str, ...]
    jobs: int = 1
    made_by: str = ""
    more: tuple[tuple[str, str], ...] = ()   # more rows of the files table: a file and what it is
    notebook: str = ""                       # the Binder link of the folder's own notebook, if it has one

    def text(self, path: str) -> str:
        """The whole page, as Markdown; `path` is the folder under examples/."""
        back = f"{self.back} {ONE_RUN}" if self.back else NOT_SENT
        return (f"# {self.title}\n\n{self.about}\n\n{flow(self.steps)}\n{self._pictures(path)}\n**What a perfect "
                f"machine gives:** {self.perfect}\n\n**What came back:** {back}\n\n{_emulate(path, self.notebook)}\n"
                f"{self._send()}\n{self._files()}\nMore: the [{SITES[self.site].title} page]"
                f"({MANUAL}{SITES[self.site].page}/) of the manual.\n")

    def _pictures(self, path: str) -> str:
        job = f"the job {DRAWN[path]}" if path in DRAWN else "the first job" if self.jobs > 1 else "the job"
        keys = ("the key a perfect machine gives most, for each job" if self.jobs > 1
                else "each key, up to six keys and then the rest as other")
        machine = ", and one run on the machine, with a bar of one shot error each way" if self.back else ""
        return (f"![The circuit of {job}](circuit.png)\n\nThe circuit of {job} as its file has it, drawn by qutip-qip: "
                f"one-qubit gates in blue, two-qubit gates in orange, then the measurements. Its title names the job "
                f"and says if anything is left out.\n\n![The share of each key from each source](outcomes.png)\n\n"
                f"The share of {keys}, from each source: a perfect machine (our emulator), QuTiP, Qrisp's emulator"
                f"{machine}.\n")

    def _sent(self) -> str:
        if self.jobs == 1:
            return "It reads the machine once, sends the job, waits for it, and stores the counts in a record."
        return ("It reads the machine once and sends order 1 alone, so you can look at it first. It then prints "
                "`Go on with: qdevices send ... --max-order N`. Start `pixi shell` at the top of the clone, come back "
                f"here, and run that line with N = {self.jobs}; no order goes twice.")

    def _send(self) -> str:
        site = SITES[self.site]
        path = flow(("./run.sh: a check, offline", "./submit.sh: asks the machine for its state, no job yet",
                     "The job goes, with a record on disk", site.runs, "./run.sh --counts"))
        return (f"## Send it to the machine\n\nThis part is for people with an account at the site, and it uses their "
                f"award.\n\n{path}\n"
                f"1. Run `./run.sh`: a dry run, with no token, that sends nothing. It needs [pixi](https://pixi.sh), "
                f"on Linux x86-64 or an Apple Silicon Mac, and a clone of the repository. It checks against "
                f"`examples/qdevices.toml` while the manifest says `MY-`, then against your config, and it counts each "
                f"measurement as a gate.\n"
                f"2. The first time, from the top of the clone: `mkdir -p ~/.config/qdevices && cp "
                f"examples/qdevices.toml ~/.config/qdevices/qdevices.toml`. The app reads its settings there. Put your "
                f"own names in that copy and in `manifest.json` here, in place of {site.names}.\n"
                f"3. Set your token, which is never printed: `set +x; export {site.token}=\"$(cat FILE)\"`, where FILE "
                f"is the file that holds your token. `./run.sh --login` says how to get one. A token is personal: "
                f"never hand it to anyone else.\n"
                f"4. Run `./submit.sh`. {self._sent()}\n5. Run `./run.sh --counts` to see what came back.\n")

    def _files(self) -> str:
        rows = [f"| `{name}` | {SITES[self.site].form} |" for name in self.files]
        made = f"\n{self.made_by}\n" if self.made_by else ""
        ran = "| `results.json` | the counts of one run on the machine, with no job id and no date |\n"
        more = "".join(f"| `{name}` | {what} |\n" for name, what in self.more)
        return ("## The files\n\n| File | What it is |\n|---|---|\n" + "\n".join(rows) + "\n" + FILES
                + (ran if self.back else "") + more + made)

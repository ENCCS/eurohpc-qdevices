"""A site with scripted answers, for the tests of the runner, and the job state it reports."""

from qdevices.sites.base import NoAnswer, Site, SiteError
from qdevices.sites.protocol import JobState

from .core import TOKEN, lines_of, turn

_FAILS = {    # the kind of a scripted submit that fails: what it raises, from the action
    "refuse": lambda a: SiteError(f"HTTP {a[1]}", status=a[1], body=a[2] if len(a) > 2 else "cz", step="submit"),
    "unknown": lambda a: SiteError(f"HTTP {a[1]}", status=a[1], body=a[2] if len(a) > 2 else "", step="submit"),
    "noid": lambda a: SiteError("the answer has no id", step="submit"),
    "noanswer": lambda a: NoAnswer("no answer", step="submit"),
    "interrupt": lambda a: KeyboardInterrupt(),
    "crash": lambda a: RuntimeError("a fault of the program"),
}


def STATE(state="RUNNING", final=False, ok=False, configuring=False) -> JobState:
    return JobState(state=state, final=final, ok=ok, configuring=configuring)


class FakeSite(Site):
    """A site with scripted answers. `submits` maps an order to an action; `states` a job id to states."""

    options = {"no_modify": bool}
    addresses = ("https://fake.invalid",)
    poll_seconds = 5.0

    def __init__(self, name: str = "euroqexa", *, submits=None, states=None, token=TOKEN, record=None,
                 read=None, max_shots=None, seconds_left=None, refuse_codes=(400,), seconds_kind="device",
                 problems=()) -> None:
        super().__init__(token)
        self.name = name
        if name == "vlq":
            self.made_step, self.submit_step = "created", "uploaded"
        self.submits = dict(submits or {})
        self.states = {k: list(v) for k, v in (states or {}).items()}
        self.calls: list = []
        self.record = record          # gives the record path, to read the disk
        self._read = read if read is not None else {"machine": "M1", "online": True, "qubits": 5}
        self.max_shots = max_shots
        self._seconds_left = seconds_left
        self.refuse_codes = refuse_codes
        self.seconds_kind = seconds_kind
        self.problems = list(problems)
        self.seen_on_disk: list = []
        self.shots: dict = {}

    def read(self) -> dict:
        self.calls.append(("read",))
        return dict(self._read)

    def validate(self, job, read):
        return list(self.problems)

    def prepare(self, job, note):
        self.calls.append(("prepare", job["order"]))
        return None

    def _last_line(self):
        return lines_of(self.record())[-1] if self.record else None

    def submit(self, job, note, prepared=None):
        order = job["order"]
        self.calls.append(("submit", order))
        self.seen_on_disk.append(self._last_line())
        action = self.submits.get(order, ("id", f"J-{order}"))
        if action[0] == "steps":
            for step, ids in action[2]:
                note(step, **ids)
                self.seen_on_disk.append(self._last_line())
            action = action[1]
        if action[0] != "id":
            failure = _FAILS.get(action[0])
            if failure is None:
                raise AssertionError(action[0])
            raise failure(action)
        self.shots[action[1]] = job["shots"]
        return action[1]

    def status(self, job_id):
        self.calls.append(("status", job_id))
        script = self.states.get(job_id)
        if not script:
            return STATE("COMPLETED", final=True, ok=True)
        item = turn(script)
        if callable(item):
            item = item()
        if isinstance(item, Exception):
            raise item
        return item

    def result(self, job_id):
        self.calls.append(("result", job_id))
        shots = self.shots.get(job_id, 10)
        return {"counts": {"1": shots}, "seconds": 1.5}

    def logs(self, job_id):
        return {"stdout.txt": f"log with {TOKEN} inside"}

    def classify(self, error):
        return "refused" if error.status in self.refuse_codes and error.step == "submit" else "unknown"

    def token_seconds_left(self):
        return self._seconds_left

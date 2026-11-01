"""Unit tables of VLQ over the fake service."""

import base64
import hashlib
import json
import pickle
import string

import httpx
import pytest
from cryptography.fernet import Fernet
from fakes import lines_of, records_of, send, write_manifest
from fakes.vlq import PASSWORDS_SEEN, TOKEN, VLQ_TEXT, FakeVLQ

from qdevices.sites.vlq import VLQ

CODES = (0, 1, 2, 3, 4, 8, 16, 32, 64, 128, 256, 512)     # each documented HEAppE state, and 0, 3 and 512
RESONATOR = "r" + chr(0xE9) + "sonateur"                   # a component whose name is not ASCII
LETTERS_AND_DIGITS = set(string.ascii_letters + string.digits)


class Scripted(FakeVLQ):
    """The fake service with `answers` of its own by path end (None: the fake answers), and each request in `seen`."""

    def __init__(self, places, answers=None, **kw):
        super().__init__(places, **kw)
        self.answers, self.seen = dict(answers or {}), []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.seen.append(request)
        for end, answer in self.answers.items():
            made = answer(request) if request.url.path.endswith(end) else None
            if made is not None:
                return made
        return super().__call__(request)


def make(tmp_path, places, clock, answers=None, **kw):
    """(fake service, manifest of one job, VLQ site over the fake service): fakes.vlq.make_vlq with one job."""
    fake = Scripted(places, answers, **kw)
    m = write_manifest(tmp_path / "m", site="vlq", jobs=(("V1", 10),), text=VLQ_TEXT)
    site = VLQ(TOKEN, "VLQ", lexis_project="TEST-LEXIS", resource="R1", clock=clock, sleep=clock.sleep,
               wait_seconds=60, transport=httpx.MockTransport(fake))
    return fake, m, site


def environment(request: httpx.Request) -> dict:
    """The environment of the job of a CreateJob request, as the fake service reads it."""
    return {e["Name"]: e["Value"] for e in json.loads(request.content)["JobSpecification"]["EnvironmentVariables"]}


def test_the_state_of_each_heappe_code(tmp_path, places, clock, golden):
    _fake, _m, site = make(tmp_path, places, clock, states={1000 + code: [code] for code in CODES})
    golden("units_vlq_states", "".join(f"{json.dumps(site.status(1000 + code))}\n" for code in CODES))


def test_each_sealed_token_opens_with_the_password_of_its_job(tmp_path, places, clock):
    fake, m, site = make(tmp_path, places, clock)
    assert send(m, site, places, clock, max_order=1) == 0
    password, opened = None, []
    for request in fake.seen:
        if request.url.path.endswith("CreateJob"):
            encoded = environment(request)["USER_JWT_PWD"]
            password = base64.b64decode(encoded).decode()
            assert len(password) == 50 and set(password) <= LETTERS_AND_DIGITS
            assert base64.b64encode(password.encode()).decode() == encoded
        elif b'filename="user_token.enc"' in request.content:
            sealed = request.content.split(b"\r\n\r\n", 1)[1].rsplit(b"\r\n--", 1)[0]
            key = base64.urlsafe_b64encode(hashlib.sha256(password.encode()).digest())
            opened.append(Fernet(key).decrypt(base64.b64decode(sealed)).decode())
    assert opened == [TOKEN, TOKEN]                # the token of the init job, then of the metered job


def table_of_the_day() -> bytes:
    """An init artefact iqm_target_attrs.pkl of plain dicts and lists: two qubits round the resonator RESONATOR."""
    qubits = ["qubit-1", "qubit-2"]
    loci = [[name, RESONATOR] for name in qubits]
    gates = {gate: {"implementations": {"default": {"loci": loci}}} for gate in ("cz", "move")}
    return pickle.dumps({"iqm_component_to_idx": {"qubit-1": 0, "qubit-2": 1, RESONATOR: 2},
                         "iqm_dqa": {"qubits": qubits, "computational_resonators": [RESONATOR], "gates": gates}})


def test_a_table_with_a_name_that_is_not_ascii_keeps_the_ascii_escapes_in_its_digest(tmp_path, places, clock):
    data = table_of_the_day()

    def download(request: httpx.Request):
        if b"/iqm_target_attrs.pkl" not in request.content:
            return None
        return httpx.Response(200, json=base64.b64encode(data).decode())

    _fake, m, site = make(tmp_path, places, clock, {"DownloadFileFromCluster": download})
    assert send(m, site, places, clock, max_order=1) == 0
    rec = records_of(places)[0]
    done = next(line for line in lines_of(rec) if line.get("step") == "init_done")
    pairs = [["qubit-1", RESONATOR], ["qubit-2", RESONATOR]]
    table = {"index": {"qubit-1": 0, "qubit-2": 1, RESONATOR: 2}, "qubits": ["qubit-1", "qubit-2"],
             "resonators": [RESONATOR], "loci": {"cz": pairs, "move": pairs}}
    canonical = json.dumps(table, sort_keys=True, separators=(",", ":"))     # the form the manual gives
    as_text = json.dumps(table, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert canonical.isascii() and not as_text.isascii()
    assert done["table"] == {"size": 3, "resonators": [2], "sha256": hashlib.sha256(canonical.encode()).hexdigest()}
    assert hashlib.sha256(as_text.encode()).hexdigest() != done["table"]["sha256"]
    assert "sonateur" not in rec.read_text()        # no name of a component reaches the record, in either form


def listing(node_drops=(), template_drops=()) -> list:
    """The fake cluster listing of the init queue alone, less these keys of the node type and of its template."""
    template = {"Name": "RunQInit", "Id": 10, "IsEnabled": True}
    node = {"Id": 2, "Name": "init_queue", "MaxWalltime": 7200, "FileTransferMethodId": 1,
            "Accounting": [{"Formula": "NumNodes * RunTime"}],
            "Projects": [{"AccountingString": "R1",
                          "CommandTemplates": [{k: v for k, v in template.items() if k not in template_drops}]}]}
    return [{"Id": 1, "Name": "C", "NodeTypes": [{k: v for k, v in node.items() if k not in node_drops}]}]


LISTINGS = {             # case: keys taken out of the node type, and of its template
    "node_no_name": (("Name",), ()),
    "node_no_name_no_id": (("Name", "Id"), ()),
    "template_no_name": ((), ("Name",)),
    "template_no_name_no_id": ((), ("Name", "Id")),
}


@pytest.mark.parametrize("case", list(LISTINGS))
def test_a_cluster_listing_that_cannot_be_read_stops_at_the_read(tmp_path, places, clock, golden, case):
    clusters = listing(*LISTINGS[case])
    answers = {"ListAvailableClusters": lambda request: httpx.Response(200, json=clusters)}
    _fake, m, site = make(tmp_path, places, clock, answers)
    assert send(m, site, places, clock, max_order=1) == 1                     # was 3 before fault 24 was fixed
    last = records_of(places)[0].read_text().splitlines()[-1]
    assert json.loads(last)["event"] == "stop" and json.loads(last)["kind"] == "read"
    golden(f"units_vlq_cluster_{case}", last + "\n")


def test_the_secrets_are_the_token_then_each_password_raw_and_in_base64_in_the_order_made(tmp_path, places, clock):
    _fake, m, site = make(tmp_path, places, clock)
    before = len(PASSWORDS_SEEN)
    assert send(m, site, places, clock, max_order=1) == 0
    made = PASSWORDS_SEEN[before:]                 # the USER_JWT_PWD of each CreateJob, the init job first
    assert len(made) == 2
    forms = [form for encoded in made for form in (base64.b64decode(encoded).decode(), encoded)]
    assert site.secrets() == [TOKEN, *forms]


@pytest.mark.parametrize("command, code, kind", [("backend_init", 1, "prepare"), ("backend_run", 2, "unknown")])
def test_a_failed_create_job_whose_answer_is_the_password_leaves_no_form_of_it_in_the_record(
        tmp_path, places, clock, command, code, kind):
    given = []          # the password of the CreateJob answered 500, and whether the secrets held it then

    def create(request: httpx.Request):
        env = environment(request)
        if env["Q_COMMAND"] != command:
            return None
        given.append((env["USER_JWT_PWD"], env["USER_JWT_PWD"] in site.secrets()))
        return httpx.Response(500, text=env["USER_JWT_PWD"])      # the bare base64 password, in no form of a pattern

    _fake, m, site = make(tmp_path, places, clock, {"CreateJob": create})
    assert send(m, site, places, clock, max_order=1) == code
    rec = records_of(places)[0]
    assert len(given) == 1 and lines_of(rec)[-1]["kind"] == kind
    encoded, held = given[0]
    assert held                                    # the password joined the secrets before its CreateJob was sent
    text = rec.read_text()
    for form in (base64.b64decode(encoded).decode(), encoded, *site.secrets()[1:]):
        assert form not in text and form[:8] not in text


UNFIT = b"OPENQASM 2.0;\nqreg q[3];\nh q[0];\nr(pi, 0) q[1];\nmove q[1], q[2];\n"
UNFIT_PROBLEMS = [       # each problem of UNFIT against a read of 2 qubits, in the order given
    "the file is not an OpenQASM 3 text",
    "the gates ['h'] are not native on VLQ (barrier, cz, measure, move, prx, r); the site does not compile",
    "the text uses r and does not declare it (gate r ... { gphase(0); })",
    "the text uses move and does not declare it (gate move ... { gphase(0); })",
    "the text declares 3 qubits, the machine has 2",
]


def test_validate_gives_each_problem_in_order_on_the_class_and_on_a_site(tmp_path, places, clock):
    _fake, _m, site = make(tmp_path, places, clock)
    unfit, fit = {"text": UNFIT, "shots": 10, "options": {}}, {"text": VLQ_TEXT, "shots": 10, "options": {}}
    assert VLQ.validate(unfit, {"qubits": 2}) == site.validate(unfit, {"qubits": 2}) == UNFIT_PROBLEMS
    assert VLQ.validate(fit, None) == site.validate(fit, None) == []


ABSENT = {               # case: the cluster listing, and what HEAppE does not list of it, in the order named
    "no_cluster": ([], "init_queue, compute_queue, RunQInit, RunQExecute"),
    "init_queue_only": (listing(), "compute_queue, RunQExecute"),
}
READ_PATHS = ["vlq-status.json", "Project", "ProjectResource", "ProjectsForCurrentUser", "ListAvailableClusters"]


def path_ends(fake: Scripted) -> list[str]:
    """The last part of the path of each request the fake service was sent, in order."""
    return [request.url.path.rsplit("/", 1)[-1] for request in fake.seen]


@pytest.mark.parametrize("case", list(ABSENT))
def test_a_listing_that_lacks_a_queue_or_template_of_a_job_stops_at_the_read(tmp_path, places, clock, case):
    clusters, absent = ABSENT[case]
    answers = {"ListAvailableClusters": lambda request: httpx.Response(200, json=clusters)}
    fake, m, site = make(tmp_path, places, clock, answers)
    assert send(m, site, places, clock, max_order=1) == 1
    last = lines_of(records_of(places)[0])[-1]
    assert (last["event"], last["kind"], last["step"]) == ("stop", "read", "read")
    assert last["error"] == f"HEAppE does not list {absent} for this token"
    assert path_ends(fake) == READ_PATHS           # no dry run and no job


def node_type(node_id: int, name: str, *templates: tuple) -> dict:
    """A node type of the fake cluster listing, with these (name, id) templates enabled for the resource R1."""
    return {"Id": node_id, "Name": name, "MaxWalltime": 7200, "FileTransferMethodId": 1,
            "Accounting": [{"Formula": "NumNodes * RunTime"}],
            "Projects": [{"AccountingString": "R1",
                          "CommandTemplates": [{"Name": t, "Id": i, "IsEnabled": True} for t, i in templates]}]}


def test_the_dry_run_job_of_a_read_is_sent_before_its_templates_are_sorted_as_texts(tmp_path, places, clock):
    nodes = [node_type(2, "init_queue", ("RunQInit", 10)), node_type(3, "compute_queue", ("RunQExecute", 11), (7, 12))]
    clusters = [{"Id": 1, "Name": "C", "NodeTypes": nodes}]
    answers = {"ListAvailableClusters": lambda request: httpx.Response(200, json=clusters)}
    fake, m, site = make(tmp_path, places, clock, answers)
    assert send(m, site, places, clock, max_order=1) == 0     # fault 10: a template named by a number, sorted as text
    assert path_ends(fake)[:len(READ_PATHS) + 1] == [*READ_PATHS, "DryRunJob"]
    read = next(line for line in lines_of(records_of(places)[0]) if line["event"] == "read")
    assert read["read"]["templates"] == [7, "RunQExecute", "RunQInit"]


UNREAD_RESULTS = {       # case: the results.pkl of the job, and the error of the stop at its result
    "not_a_pickle": (b"artefact", "a result file cannot be read: the pickle cannot be read: UnpicklingError"),
    "no_counts": (pickle.dumps([]), "the result files do not give the counts and the device seconds; the job is "
                                    "finished, a resume reads them again"),
}


@pytest.mark.parametrize("case", list(UNREAD_RESULTS))
def test_result_files_that_give_no_result_stop_the_order_and_leave_it_open(tmp_path, places, clock, case):
    data, error = UNREAD_RESULTS[case]
    fake, m, site = make(tmp_path, places, clock)
    fake.results_pkl = data
    assert send(m, site, places, clock, max_order=1) == 1
    last = lines_of(records_of(places)[0])[-1]
    assert (last["event"], last["kind"], last["step"], last["error"]) == ("stop", "result_error", "result", error)


def test_the_logs_of_a_failed_job_keep_each_file_in_order_and_mark_one_that_cannot_be_read(tmp_path, places, clock):
    def download(request: httpx.Request):
        return httpx.Response(500, text="no") if b"/stderr.txt" in request.content else None

    _fake, m, site = make(tmp_path, places, clock, {"DownloadFileFromCluster": download}, states={102: [32]})
    assert send(m, site, places, clock, max_order=1) == 2     # Failed: the rule refusal stops the call
    failed = next(line for line in lines_of(records_of(places)[0]) if line["event"] == "failed")
    assert list(failed["logs"].items()) == [("stdout.txt", "artefact"), ("stderr.txt", "<unavailable>"),
                                            ("quantum_task_progress.log", "artefact")]


def test_the_cut_of_a_log_leaves_no_end_of_the_token_in_the_failed_line(tmp_path, places, clock):
    log = (TOKEN + "x" * 1980).encode()           # the cut keeps the last 20 characters of the token

    def download(request: httpx.Request):
        if b"/stdout.txt" in request.content:
            return httpx.Response(200, json=base64.b64encode(log).decode())
        return None

    _fake, m, site = make(tmp_path, places, clock, {"DownloadFileFromCluster": download}, states={102: [32]})
    assert send(m, site, places, clock, max_order=1) == 2
    text = records_of(places)[0].read_text()
    failed = next(line for line in lines_of(records_of(places)[0]) if line["event"] == "failed")
    assert failed["logs"]["stdout.txt"].endswith("x" * 1980) and TOKEN[-8:] not in text

"""The calibration set of a VLQ job: read from its results.pkl, kept on the result line, seen by the rules."""

import pickle
import time
import uuid

from fakes import FakeSite, lines_of, records_of, send, write_manifest
from fakes.vlq import CALIBRATION, Counts, Experiment, Parameters, Results, go, make_vlq, results_file

from qdevices.sites import pickle_reader
from qdevices.sites.vlq.results import MAX_DEPTH, ResultsFile

OTHER = "00000000-0000-4000-8000-000000000001"      # synthetic


class Damaged:
    """Pickles as a uuid.UUID with the state it is given, as a damaged file could hold one."""

    def __init__(self, state):
        self.state = state

    def __reduce__(self):
        return uuid.UUID, (), self.state


def holding(*ids) -> bytes:
    """A results file with one result for each value of calibration_set_id given."""
    return pickle.dumps(Results(*(Experiment(Counts({"1": 5}), Parameters(i)) for i in ids)))


def calibration_set_of(data) -> str | None:
    """The calibration set that the search of the reader finds in a results file, or None for a file it refuses."""
    try:
        return ResultsFile.parse(data).calibration_set
    except pickle_reader.PickleRefused:
        return None


def test_the_uuid_in_the_parameters_of_a_result_is_found():
    assert calibration_set_of(results_file()) == CALIBRATION        # its state: int and is_safe
    assert calibration_set_of(holding(uuid.UUID(CALIBRATION))) == CALIBRATION    # int alone


def test_a_text_in_the_form_of_a_uuid_is_found_in_canonical_form():
    for text in (CALIBRATION.upper(), "{" + CALIBRATION + "}", "urn:uuid:" + CALIBRATION, CALIBRATION.replace("-", "")):
        assert calibration_set_of(holding(text)) == CALIBRATION


def test_no_field_and_no_id_give_none():
    assert calibration_set_of(pickle.dumps([Counts({"1": 10})])) is None
    for value in (None, "not an id", 7, b"\x00" * 16):
        assert calibration_set_of(holding(value)) is None


def test_a_file_that_is_not_read_or_a_damaged_id_gives_none_and_no_exception():
    for data in (b"not a pickle", None, pickle.dumps(list(range(3)))[:-3]):
        assert calibration_set_of(data) is None
    for state in ({"int": -1}, {"int": 1 << 128}, {"int": True}, {"int": "1"}, {"__dict__": 5}, {}, None):
        assert calibration_set_of(holding(Damaged(state))) is None


def test_two_different_ids_give_none_and_one_id_given_twice_gives_it():
    assert calibration_set_of(holding(uuid.UUID(CALIBRATION), uuid.UUID(OTHER))) is None
    assert calibration_set_of(holding(uuid.UUID(CALIBRATION), CALIBRATION.upper())) == CALIBRATION
    assert calibration_set_of(holding(uuid.UUID(CALIBRATION), None)) == CALIBRATION


def test_the_search_reads_the_field_down_to_max_depth_and_no_deeper():
    held = {"calibration_set_id": CALIBRATION}
    for _ in range(MAX_DEPTH):
        held = [held]                                 # the dict that holds the field at depth MAX_DEPTH
    assert calibration_set_of(pickle.dumps(held)) == CALIBRATION
    assert calibration_set_of(pickle.dumps([held])) is None


def test_a_long_text_is_not_parsed_so_many_fields_that_share_it_keep_the_search_short():
    edge = "-" * (pickle_reader.ID_TEXT - len(CALIBRATION)) + CALIBRATION     # the uuid module drops each hyphen
    assert calibration_set_of(holding(edge)) == CALIBRATION
    assert calibration_set_of(holding("-" + edge)) is None
    text = "-" * (8 * 1024 * 1024) + CALIBRATION
    many = [[{"calibration_set_id": text} for _ in range(64)] for _ in range(64)]    # 4,096 fields, one text
    start = time.monotonic()
    assert calibration_set_of(pickle.dumps(many)) is None
    assert time.monotonic() - start < 5


def test_the_result_line_and_the_state_of_a_rule_hold_the_calibration_set(tmp_path):
    places, clock, _fake, m, site = make_vlq(tmp_path)
    seen = []

    def after_result(job, result, state):
        seen.append((result["calibration_set"], state["results"][str(job["order"])]))
        return {"rule": "look", "passed": True}

    assert go(m, site, places, clock, max_order=1, user_rules={"after_result": after_result}) == 0
    result = next(e for e in lines_of(records_of(places)[0]) if e["event"] == "result")
    assert result["calibration_set"] == CALIBRATION and result["counts"] == {"1": 10}
    assert seen == [(CALIBRATION, {"id": 102, "counts": {"1": 10}, "seconds": 0.42, "calibration_set": CALIBRATION})]


def test_a_results_file_with_no_calibration_set_still_gives_the_result(tmp_path):
    places, clock, fake, m, site = make_vlq(tmp_path)
    fake.results_pkl = pickle.dumps([Counts({"1": 10})])
    assert go(m, site, places, clock, max_order=1) == 0
    result = next(e for e in lines_of(records_of(places)[0]) if e["event"] == "result")
    assert result["calibration_set"] is None and result["counts"] == {"1": 10} and result["seconds"] == 0.42


def test_the_other_sites_give_no_calibration_set(tmp_path, places, clock):
    seen = []

    def after_result(job, result, state):
        seen.append(state["results"][str(job["order"])])
        return {"rule": "look", "passed": True}

    assert send(write_manifest(tmp_path / "m"), FakeSite(), places, clock, max_order=1,
                user_rules={"after_result": after_result}) == 0
    result = next(e for e in lines_of(records_of(places)[0]) if e["event"] == "result")
    assert "calibration_set" not in result and seen == [{"id": "J-1", "counts": {"1": 10}, "seconds": 1.5}]

"""The stop at a lost order says where to look for its job: the site's note, then the `resolve` command."""

from fakes import FakeSite, events, records_of, send, write_manifest
from fakes.piastq import Broker

from qdevices.screen import quoted
from qdevices.sites.piastq import PiastQ


def lost_order(tmp_path, places, clock, site: str):
    """A record whose order 1 is lost: an interrupt in its job request."""
    m = write_manifest(tmp_path / "m", site=site, jobs=(("J1", 10),))
    assert send(m, FakeSite(site, submits={1: ("interrupt",)}), places, clock, max_order=1) == 130
    return m, records_of(places)[0]


def test_the_stop_at_a_lost_order_says_to_look_in_the_job_list_of_the_site(tmp_path, places, clock):
    m, rec = lost_order(tmp_path, places, clock, "euroqexa")
    assert send(m, FakeSite(), places, clock, resume=rec) == 1
    stop = events(rec, "stop")[-1]
    assert stop["kind"] == "lost" and stop["reason"] == (
        "order 1 (J1) has a 'submitting' line and no job id: the request may have reached the site. It is never "
        "sent again. Look for it in the job list of the site, then record what you found: qdevices resolve "
        f"{quoted(rec)} 1 --job ID (or --none)")


def test_the_stop_at_a_lost_piastq_order_says_to_ask_pcss(tmp_path, places, clock):
    m, rec = lost_order(tmp_path, places, clock, "piastq")
    broker = Broker()
    assert send(m, broker.site(), places, clock, resume=rec) == 1
    assert PiastQ.lost_note == "The broker has no list of tasks: ask PCSS whether a task was made"
    assert ("It is never sent again. The broker has no list of tasks: ask PCSS whether a task was made, then "
            f"record what you found: qdevices resolve {quoted(rec)} 1 --job ID (or --none)") in \
        events(rec, "stop")[-1]["reason"]
    assert broker.requests == []

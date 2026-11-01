"""G4: the facts of each registered machine that the registry cannot check when it is made, and the registry itself.

These tests check a class against its own code, the readers of a record line and the other classes. The registry
and Profile get copies of the three classes, each with one fault, and never a machine of their own.
"""

import dataclasses
import json
import re
import types

import httpx
import pytest
from fakes import TOKEN, FakeClock

from qdevices import config, ledger, manifest, monitor, sites
from qdevices.runner import resume
from qdevices.sites.facts import SECONDS, Key
from qdevices.sites.protocol import INIT_JOB, JOB, NODE_SECONDS, TABLE_NOTE, SiteProtocol

NAMES = list(sites.SITES)
# Keys of a manifest and of the lines of a record, and keys that a reader of a line reads on any event. A route key
# is on every line of a record, so it must be none of them.
LINE_KEYS = frozenset({"format", "site", "machine", "project", "run", "jobs", "path", "folder", "sha256", "extra",
                       "app", "event", "utc", "order", "name", "step", "id", "kind", "reason", "state", "shots",
                       "options", "proposal", "seconds", "device_seconds", "wall_seconds", "task", "status",
                       "state_name", "missed", *ledger.ID_KEYS, *manifest.JOB_KEYS, INIT_JOB, TABLE_NOTE, NODE_SECONDS,
                       JOB})
EUROQEXA, VLQ, PIASTQ = (sites.SITES[name] for name in ("euroqexa", "vlq", "piastq"))


def derived(base: type, **attrs: object) -> type:
    """A copy of a registered class with these attributes in its own body, made as a class statement makes it."""
    return types.new_class(base.__name__, (base,), exec_body=lambda body: body.update(attrs))


def copy_of(base: type, **facts: object) -> type:
    """A copy that sets the name, token variable and profile of its class in its own body, with these facts changed."""
    return derived(base, name=base.name, token_env=base.token_env, profile=dataclasses.replace(base.profile, **facts))


@pytest.mark.parametrize("name", NAMES)
def test_each_class_sets_its_facts_in_its_own_body_and_lives_in_the_module_of_its_name(name):
    cls = sites.SITES[name]
    assert {"name", "token_env", "profile"} <= set(vars(cls)) and cls.name == name
    assert cls.__module__ == f"qdevices.sites.{name}" or cls.__module__.startswith(f"qdevices.sites.{name}.")


def test_the_titles_are_unique_and_each_token_variable_is_upper_case():
    titles = [cls.profile.title for cls in sites.SITES.values()]
    assert len(set(titles)) == len(titles)
    assert [cls.token_env for cls in sites.SITES.values() if not re.fullmatch(r"[A-Z][A-Z0-9_]*", cls.token_env)] == []


def test_each_name_fits_the_site_column_of_the_usage_table():
    head = monitor.usage([], config.parse(""))[0]
    assert [name for name in NAMES if len(name) >= head.index("project")] == []


@pytest.mark.parametrize("name", NAMES)
def test_the_route_keys_are_no_key_that_a_line_holds_or_that_a_reader_of_a_line_reads(name):
    keys = [key for key, _ in sites.SITES[name].profile.route_keys]
    assert [key for key in keys if key in LINE_KEYS or resume.ID_IN_LINE.search(json.dumps({key: "x"}))] == []


def test_no_config_key_of_a_class_is_a_key_that_every_site_takes():
    common = {key.name for key in config.COMMON}
    assert [(name, key.name) for name, cls in sites.SITES.items() for key in cls.profile.config_keys
            if key.name in common] == []


@pytest.mark.parametrize("name", NAMES)
def test_the_seconds_steps_and_token_rule_of_a_class_go_with_the_code_that_needs_them(name):
    cls = sites.SITES[name]
    assert cls.seconds_kind in SECONDS                          # the words of its seconds in the usage text
    assert (cls.made_step is None) == (cls.submit_step is None) == (cls.profile.configuring_state is None)
    assert cls.profile.token_min_seconds is None or cls.token_seconds_left is not SiteProtocol.token_seconds_left


@pytest.mark.parametrize("name", NAMES)
def test_making_a_site_and_closing_it_sends_no_request_and_leaves_no_abstract_step(name):
    def refuse(request: httpx.Request) -> httpx.Response:
        pytest.fail(f"a request when a site is made or closed, outside the lock: {request.method} {request.url}")

    clock = FakeClock()
    made = sites.make_site(None, name, TOKEN, clock=clock, sleep=clock.sleep, site_config=config.parse("")[name],
                           transport=httpx.MockTransport(refuse))
    assert type(made) is sites.SITES[name]
    made.close()


@pytest.mark.parametrize("classes, words", [
    ((EUROQEXA, EUROQEXA), "the site name 'euroqexa' is given twice"),
    ((EUROQEXA, derived(PIASTQ, name="piastq", token_env=EUROQEXA.token_env, profile=PIASTQ.profile)),
     "EuroQExa and PiastQ share MQSS_TOKEN with other addresses"),
    ((derived(VLQ, name="vlq", token_env=VLQ.token_env),), "VLQ does not set profile = Profile(...)"),
    ((derived(VLQ, profile=VLQ.profile),), "VLQ does not set name in its own body"),
    ((derived(VLQ, name="VLQ", token_env=VLQ.token_env, profile=VLQ.profile),),
     "the site name 'VLQ' is not of the form"),
    ((derived(VLQ, name="tenletters", token_env=VLQ.token_env, profile=VLQ.profile),),   # wider than the usage column
     "the site name 'tenletters' is not of the form"),
    ((EUROQEXA, copy_of(PIASTQ, older_machines=("EQE1",))), "EuroQExa and PiastQ both name the older machine 'EQE1'"),
    ((copy_of(EUROQEXA, config_keys=(Key(name="window", kind=str),)), PIASTQ),
     "EuroQExa and PiastQ declare the config key 'window' with other rows"),
    ((VLQ, copy_of(PIASTQ, status_rows=VLQ.profile.status_rows)), "VLQ and PiastQ both set status_rows"),
], ids=["name twice", "token of other addresses", "inherited profile", "inherited name", "capitals", "ten letters",
        "older machine twice", "config key of two rows", "two status files"])
def test_the_registry_refuses_a_class_it_cannot_register_and_names_why(classes, words):
    with pytest.raises(TypeError) as caught:
        sites._registry(classes)
    assert str(caught.value).startswith("the sites cannot be registered: ") and words in str(caught.value)


def test_the_registry_takes_the_classes_in_the_order_given():
    assert list(sites._registry((EUROQEXA, VLQ, PIASTQ)).items()) == list(sites.SITES.items())
    assert list(sites._registry((PIASTQ, VLQ, EUROQEXA))) == ["piastq", "vlq", "euroqexa"]


@pytest.mark.parametrize("facts", [
    {"login": ()}, {"billing": "no rule"}, {"token_label": "a token"}, {"member_key": "project"},
    {"route_keys": (("project",),)}, {"token_waits": 2}, {"secret_patterns": (("secret", "[hidden]"),)},
], ids=["no login line", "billing not a Rule", "label with no expiry", "member not a route key", "route not a pair",
        "waits with no token rule", "pattern not compiled"])
def test_a_profile_that_breaks_one_of_its_rules_fails_when_its_class_is_made(facts):
    with pytest.raises(TypeError, match="the profile 'Piast-Q'"):
        dataclasses.replace(PIASTQ.profile, **facts)


def test_a_secret_pattern_whose_replacement_names_a_group_it_has_not_fails_when_its_class_is_made():
    with pytest.raises(re.error):
        dataclasses.replace(PIASTQ.profile, secret_patterns=((re.compile("(secret)"), r"\g<2>"),))

"""An example rules file: stop the run if a Bell job gives the two even outcomes in less than half its shots.

A rule gets plain dicts and answers with a verdict. A verdict that does not pass stops the run. Use it with:

    qdevices send examples/euroqexa-three-jobs/manifest.json --live --max-order 3 --rules examples/rules_bell.py
"""


def after_result(job: dict, result: dict, state: dict) -> dict:
    """The verdict on one result: a Bell job passes when 00 and 11 hold at least half of its shots."""
    if not job["name"].startswith("BELL"):
        return {"rule": "bell", "passed": True}
    counts = result["counts"]
    even = counts.get("00", 0) + counts.get("11", 0)
    share = even / job["shots"]
    return {"rule": "bell", "passed": share >= 0.5, "share": share,
            "reason": f"00 and 11 in {share:.2f} of the shots, below 0.5"}

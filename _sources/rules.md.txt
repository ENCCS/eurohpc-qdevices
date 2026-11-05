# Rules

Give the rules of an experiment in a Python file, with `qdevices send ... --rules FILE`. A rule decides
whether a run goes on. The generic rules of the app always run too.

```bash
qdevices send examples/euroqexa-three-jobs/manifest.json --live --max-order 1 --rules examples/rules_bell.py
qdevices send examples/euroqexa-three-jobs/manifest.json --live --resume RECORD --max-order 3 --rules examples/rules_bell.py
```

:::{warning}
A rules file runs with your rights and can read the rest of the environment. The token variable is
already deleted when the file is imported. Give only a file you have read.
:::

## The functions

| Function | Called | With |
|---|---|---|
| `before_call(read)` | once a call, before its first job | the read of the machine |
| `before_job(job, state)` | before each job is sent | the job, the state of the run |
| `after_result(job, result, state)` | after each result line is on disk | the job, the result, the state |
| `on_refusal(job, info)` | after a refusal, a failed job, or a job never submitted | the job, what happened |

Each gets plain dicts (no site object, no token) and answers with a **verdict**:

```python
{"rule": "bell", "passed": True}
{"rule": "bell", "passed": False, "reason": "00 and 11 in 0.31 of the shots"}
{"rule": "pick", "passed": True, "skip": [4, 5]}
```

- A verdict that does not pass stops the run, with exit code 2. Its reason is in the record.
- `skip` names orders not yet sent: they are never sent in that record. An order that was sent, or that
  does not exist, stops the run.
- A failed verdict: a function that raises, an answer that is not a verdict, a key that is not a text, or
  the key `self`.
- Any other key is kept in the `rule` line, but not a key the line already has (`event`, `utc`, `app`,
  `site`, `machine`, `project`, `point`, `order`, and on VLQ `lexis_project` and `resource`). A `note` is
  also printed, as a `NOTE` line after the line of the rule.
- At `before_call`, `before_job` and `after_result`, every generic rule and your rule must pass. Your
  `on_refusal` replaces the generic one, so an experiment can let a refusal go on.

| Argument | What it holds |
|---|---|
| `job` | the job of the manifest (`order`, `name`, `file`, `sha256`, `shots`, `options`, and any other key you gave it), without the circuit text |
| `result` | the result line, with `counts` (bit strings to counts) and `seconds`; on VLQ also `calibration_set`, or `None` ({doc}`vlq`) |
| `state` | `site`, `machine`, `project`, `used_seconds`, `budget_seconds`, `job_seconds_limit`, `wait_seconds`, `site_max_shots`, `max_shots`, `max_shots_times_gates` (3,000,000 on Euro-Q-Exa, `None` elsewhere), `gate_count` (the gate operations of the text as the app counts them, or `None`), `token_seconds_left`, `in_window`, `now_utc`, `results` (by order, each with `id`, `counts`, `seconds`, and on VLQ `calibration_set`), `sent`, `skipped` and `record` (the path of the record) |
| `info` | `kind` (`refused`, `failed` or `not_submitted`), `id` and `reason`; for a refusal also `http_status` and `body` (filtered, at most 200 characters); for a failed job also `state` |

**Bit order.** A rule that reads a bit by its position must do so per site. On Piast-Q, qubit 0 is the
leftmost character of each key of `counts`: element i of a shot is qubit i (release 1.15.0 of the maker's
client library), and the app joins the shot in that order. On Euro-Q-Exa and VLQ the keys are as the
site gives them; LRZ publishes no bit order. On Euro-Q-Exa, as measured with this app and not published by
LRZ, a key reads q[n-1] ... q[0], so q[0] is the rightmost character: a job with H on q[2] varied only the
leftmost. On VLQ a key reads c[n-1] ... c[0], so c[0] is the rightmost character; the examples measure q[i]
into c[i]. IT4I's guide gives no bit order. Jobs of six bits showed it, though not with this app: one that
flipped only the qubit read into c[0] gave `000001` in most shots. The app reads the counts from the same
result file of the site, in the same way. Qrisp's label of a variable reads q[0] first, so reverse a key to
compare it with `get_measurement` ({doc}`qrisp`).

## The generic rules

| Point | Rule | Passes when |
|---|---|---|
| `before_call` | `machine` | Euro-Q-Exa: the site gives the machine as online; Piast-Q: its name is in the broker's list ({doc}`piastq`); VLQ: the token is a member of the LEXIS project |
| `before_call` | `site_status` | VLQ: no flag of the status file is `false`; a file that cannot be read passes with a note ({doc}`vlq`). Other sites: it passes |
| `before_job` | `shots` | the shots are within the limit of the site and `max_shots` |
| `before_job` | `shots_times_gates` | Euro-Q-Exa: the shots times the gate operations of the text (`gate_count`) are at most 3,000,000; a text whose gates cannot be counted passes with a note ({doc}`euroqexa`). Other sites: it passes |
| `before_job` | `budget` | the seconds used so far plus `job_seconds_limit` stay within `budget_seconds` ({doc}`billing-and-usage`) |
| `before_job` | `token` | VLQ only: the token has 30 minutes or more left, or twice `wait_seconds` when that is longer, as the init job and the metered job each wait up to `wait_seconds`; the reason names the minutes needed |
| `before_job` | `window` | Piast-Q only, when a window is set: the time is inside it |
| `after_result` | `all_shots` | the result has counts by bit string, and all the shots asked came back |
| `after_result` | `job_time` | the job has a measured time, from 0 to `job_seconds_limit`; above it, the reason names `qdevices resolve ... --over-limit` ({doc}`billing-and-usage`). After a stop the result is final, and a resume with `--max-order` goes on with the next order |
| `on_refusal` | `refusal` | never: a refusal, a failed job or a job never submitted stops the run |

## The example file

`examples/rules_bell.py` stops the run if a Bell job gives the two even outcomes in less than half its
shots:

```{literalinclude} ../examples/rules_bell.py
:language: python
```

(rules-in-record)=

## The rules file in the record

The record is held to the rules file of its first call. Its start line holds `rules_file`: the path and
SHA-256 of that file, or `null` with no `--rules`. The SHA-256 covers that file alone, not the modules it
imports. The app reads the file once and runs the bytes it hashes.

| Call | Rules file |
|---|---|
| a resume that sends (`--max-order N`) | must be the one the record is held to, or it is refused before anything is sent: give that file with `--rules`, or no `--rules` when it is none. With the same path, the file has changed: put back the file with the SHA-256 that the refusal gives |
| a resume with `--new-rules` | changes it on purpose: the resume line holds the new file in `rules_file` and the old one in `rules_before` (`null` for none), and the record is held to the new one. Refused without `--resume` (exit code 1) |
| a resume that collects only | never refused for its rules file |
| the commands the app prints (`Go on with: ...`, and `Collect with: ...` after an interrupt) | give `--rules` with the file the record is held to, each path quoted for the shell, so that a resume with them runs the rules on what it collects |

```bash
qdevices send MANIFEST --live --resume RECORD --max-order N --rules FILE --new-rules
```

Each resume line holds `rules_file`, `new_rules` (`true` with `--new-rules`) and `rules_note`, the note the
app printed about the rules file, if any. A record of an older version of the app has no `rules_file`. It
is held to the rules file of its first resume that sends or gives `--new-rules`; that resume is not refused,
and its line holds a note and no `rules_before`. A resume that collects only before then sets nothing, and
its line and the commands it prints hold its rules file, with a note.

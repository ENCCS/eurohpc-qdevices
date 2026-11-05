# Manifests and records

Write a **manifest** to say what to send. The app writes a **record** of what was sent and what came back.
The app never changes a manifest, and you never change a record.

## The manifest

One JSON file, next to the circuit files it names:

```json
{"format": "qdevices/1", "site": "euroqexa", "machine": "EQE1", "project": "MY-PROJECT",
 "jobs": [{"order": 1, "name": "X", "file": "X.qasm", "sha256": "...", "shots": 100,
           "options": {"no_modify": false}}]}
```

| Key | What it holds |
|---|---|
| `format` | `"qdevices/1"` |
| `site` | `"euroqexa"`, `"vlq"` or `"piastq"` |
| `machine` | the machine name at the site: `"EQE1"`, `"VLQ"` or `"AQT"` |
| `project` | your project; it must be listed in `projects` of the config |
| `lexis_project`, `resource` | VLQ only, and needed there: the LEXIS project the device time is booked on, and the resource ({doc}`vlq`) |
| `run` | the name of the run folder of the records; when absent, the name of the folder of the manifest |
| `layout` | optional, Euro-Q-Exa: the layout the texts were written for ({ref}`layout-pin`) |
| `jobs` | the list of jobs, below |
| any other key | kept, and copied to the start line of the record (the example `euroqexa-three-jobs` has a `"note"`) |

| Key of a job | What it holds |
|---|---|
| `order` | the whole numbers 1 to N, in sequence, without gaps (not `1.0` or `true`) |
| `name` | letters, digits, `_` and `-` only |
| `file` | a file name next to the manifest (no folder part): one circuit, in the form the site takes |
| `sha256` | the SHA-256 of the file, 64 lower-case hex digits |
| `shots` | a whole number of 1 to 1,000,000,000 |
| `options` | optional: the options of the site. Euro-Q-Exa has `no_modify` ({doc}`euroqexa`); VLQ and Piast-Q have none |
| any other key | kept; a rules file sees it ({doc}`rules`) |

Get the SHA-256 with `shasum -a 256 X.qasm` (macOS) or `sha256sum X.qasm` (Linux). The dry run prints the
SHA-256 it finds when it differs. The app checks the file again just before it is sent: a file that has
changed is not sent.

(layout-pin)=

### The layout pin

Run `qdevices check euroqexa --live --manifest FILE`. It prints the layout of the machine and the line that
pins it, `"layout": {"layout_sha256": "...", "qubits": N, "pairs": M}`: put that line in the manifest. The
dry run compares the pin with the saved read (with no read, only its form), and a live call with its own
read. Another layout fails the check, and nothing is sent ({doc}`euroqexa`); `qubits` and `pairs` are then
printed. When the machine has changed, a text may act on other qubits: read it again, check the texts
against the new layout, then pin it. A record that has sent jobs cannot go on with a changed manifest
(`send` in {doc}`commands`).

`layout_sha256` is the SHA-256, in hex, of one UTF-8 text: `qubits=N;pairs=`, then each coupled pair once
as `a-b`, the lower index first, the pairs sorted and joined by commas. For 3 qubits coupled 0-1 and 1-2:
`qubits=3;pairs=0-1,1-2`.

(records)=

## The records

Each run has its records in `~/.local/share/qdevices/records/<site>/<run>/`, one `run_<UTC>.jsonl` each.
`<run>` is the `run` key of the manifest, or the name of its folder. Each event is one JSON line, synced
to disk before the next request ({doc}`live-runs`).

A line that was cut (for example by a crash), or is not UTF-8, is passed over. A resume prints each cut
line as a `NOTE`, with the job id it holds, which may be cut too. The resume line keeps them in
`cut_lines`: `line`, `text` (the first 120 characters), `job_id` and `job_id_may_be_cut`.

| Line | Written |
|---|---|
| `start` | once, at the start: the version, the host, the path, device and inode of the record, the manifest and its SHA-256, the SHA-256 of each file, the jobs, the extra keys of the manifest, the fixed addresses of the site, and the rules file ({ref}`rules-in-record`) |
| `resume` | at the start of each later call, with the rules file ({ref}`rules-in-record`) |
| `read` | the read of the machine before the first job of a call, and `notes` when the check of the jobs against it noted something |
| `rule`, `skip` | each verdict of a rule, with its `note` if any, and the orders a rule names to skip |
| `submitting` | before the first request of a job |
| `step`, `init` | each step of a VLQ job (created, uploaded) and of its init job, before the next request; the `init_done` line also holds what was read of the table of the day ({doc}`vlq`) |
| `submitted` | the job id, as soon as the answer is read |
| `status` | each state read while waiting; a missed poll ({doc}`live-runs`) when the kind of failure changes, with `missed` and the error |
| `result` | the counts and the seconds; for VLQ also `calibration_set`, or `null` ({doc}`vlq`). The bit order of the counts is in {doc}`rules` |
| `refused`, `failed`, `not_submitted` | a job the site refused, a job that failed, a VLQ job never submitted |
| `resolved` | your decision with `qdevices resolve`; with `--over-limit`, `--expired`, `--unreadable` and `--gone`, the seconds the order counts with from then on (`counted_seconds`). For a record of another runner it is in a file of the app (below) |
| `stop` | the end of a call before every order is final, with the reason and its kind |
| `end` | the normal end of a call |

## The reads

`qdevices check SITE --live` stores each read in `~/.local/share/qdevices/reads/<site>/read_<UTC>.json`,
through the token filter ({ref}`tokens`). A read of Euro-Q-Exa also holds `layout_sha256` and `pairs`
beside `qubits`; a read of VLQ holds `status`, from the status file of the site ({doc}`vlq`). The list of
machines of Euro-Q-Exa (a check without `--manifest`) is stored as `list_<UTC>.json`; the dry run does
not take it.

In records and reads, a number that is not finite is written as the text `"NaN"`, `"Infinity"` or
`"-Infinity"`, so each line and each read is standard JSON.

## Records of other runners

Give the record or its folder to `qdevices runs` or `qdevices usage`, or list it in `older_records` of the
config ({doc}`configuration`). Listed records also count in the budget and the open-order check of a send
to their own site. A record of another site in a listed folder is passed over. A record whose site cannot
be told counts for each site that lists it.

- In the records folder of the app, the app reads only its own records (`run_<UTC>.jsonl`).
- Below a folder of `older_records` or a `PATH`, it reads the files named `run*.jsonl`, and every other
  `.jsonl` file whose first line is a start line. Give any other record by its own path.
- One `.jsonl` file below the folder that cannot be read (no read permission, a broken link, or a first
  line longer than 1 MiB) makes the whole folder unreadable, even if it is not a record. A call that sends
  to its site is then refused ({doc}`commands`).
- Each record counts once, by its real path. Two copies in two folders count twice: list each record once.
- An `expired` line of another runner (the site does not know the job) makes an order with no result
  final. It then counts at `job_seconds_limit`.

The app never writes a record of another runner. A decision of `qdevices resolve` on it ({ref}`resolving`)
goes to `~/.local/share/qdevices/records/<site>/older_decisions.jsonl`, as a `resolved` line that names
the record by the SHA-256 of its first line and of the lines read (`start_sha256`, `lines`,
`lines_sha256`), the job id (`decided_id`) and its path. The app adds the line when it reads the record
while the order is as decided on, also for a copy that starts with the same lines. The file of decisions
is never read as a record.

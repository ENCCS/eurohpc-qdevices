# VLQ (IT4Innovations)

**Official pages**

- [IT4Innovations: VLQ access documentation](https://docs.it4i.cz/en/docs/clusters/vlq/access)
- [IT4Innovations: Estimating Consumption on VLQ](https://docs.it4i.cz/en/docs/clusters/vlq/vlq-consumption-guide)
- [IT4Innovations: VLQ Calibration and Health](https://docs.it4i.cz/en/docs/clusters/vlq/calibration_health)
- [IT4Innovations: the VLQ calibration sets, by id](https://extranet.it4i.cz/vlq-calibration/)
- [IT4Innovations: status page](https://status.it4i.cz/status/it4i), with a monitor for VLQ that the app does not read
- Support: [IT4Innovations Help and Support](https://docs.it4i.cz/en/docs/general/support), with the support address, the request tracker and what to put in a request

To get an account and a first job: the lesson page
[A few details on VLQ](https://enccs.github.io/eurohpc-quantum-devices-access-hpcqc/vlq/).

| | |
|---|---|
| Access | LEXIS UserOrg (`https://api.lexis.tech/userorg/api`) for the project membership and the resource; HEAppE (`https://quantum.heappe.it4i.cz/heappe/heappe`) for the jobs. The base path is doubled, as the API description of the instance gives it |
| Token | a LEXIS access token, in `LEXIS_TOKEN`. On IT4I's access page it comes from the LEXIS Python client: `LexisSession().get_access_token()` opens a login page for your MyAccessID account (or you open the address it prints), and returns the token once you have logged in. It may be saved and reused. No page gives the life of a token: `qdevices check vlq` shows the minutes left, and the rule `token` needs enough ({doc}`rules`). When it stops a call, get a new token, then resume |
| Manifest | `"machine": "VLQ"`, `"lexis_project"` and `"resource"`. The device time is booked on the LEXIS project, so it must be in `lexis_projects` of `qdevices.toml`. A live check needs the manifest: `qdevices check vlq --live --manifest MANIFEST` |
| Limits | IT4I gives no limit on the shots or circuits of a job, or the jobs in a queue. The app holds no shot limit for VLQ; `max_shots` still applies ({doc}`configuration`). It asks for a wall time of 60 s for the init job and 1800 s for the metered job, each at most the longest of its queue |
| Billing | at worst `max(shots x 400 us, 0.9 s)` per job (IT4I consumption guide, {doc}`billing-and-usage`) |
| Versions | the app is written for HEAppE V6.3.3, the version of that API description, and for the command templates `RunQInit` and `RunQExecute` of the service. The service plans "the major overhaul involving QScheduler" for its version 1.0.0; when VLQ moves to it is not published |

**The token at the site.** The VLQ service needs the token inside each job folder, in its own envelope
(Fernet, with a key from a password of the job), and the envelope password in the job's environment. So the
token is at the site in a form the site can open: this is the scheme of the service. The app never writes
the job's environment to a record. By the public code of the service, the job script deletes the token
file, `user_token.enc`, once it has read the token, and in any case when it ends.

## The circuit

One OpenQASM 3 circuit per job, in native gates only: `r` (PRX), `cz` and `move` between a qubit and the
resonator, and measure. Declare `r` and `move` as gates with an empty body (`gphase(0)`). VLQ does not
compile or route, so register index i is the component of index i in the table of the init job of the day.
No IT4I or maker page prints that table, and it can change with the calibration set. The example files
`vlq-bell` and `vlq-ghz` take QB1 to QB24 at 0 to 23 and the resonator COMPR1 at 24 (a register of 25);
after the init job the app checks each text against the table of the day (below).

The maker's software that runs the job still checks it; the app does not make these checks. By the maker's
public defaults, `move` gates come in pairs, with no gate on the moved qubit and no other `move` on the
resonator between the two. The maker's server rejects a circuit estimated to take longer than the shortest
T2 of its qubits times a server value, which is not published, and the release on VLQ is not published.

## An order is two jobs

An init job (`backend_init`, in the init queue) writes two artefacts of the service, and the metered job
(`backend_run`, in the compute queue) needs them. The app carries them as bytes. It reads one,
`iqm_target_attrs.pkl`, with the restricted reader (below); no artefact goes through the standard loader.
By the public service code an init job uses no device time, but HEAppE can book its classical node time
(NumNodes x RunTime), which a site utilisation report may count. `qdevices usage` shows init jobs and their
node time apart. Each new try after a stop makes another init job, which books node time.

**The table of the day.** After the init job, the app reads from `iqm_target_attrs.pkl` the index of each
component, the qubits, the resonator, and the loci of `cz` and `move`. Before the metered job is made, it
checks that `r`, `prx` and `measure` act on the index of a qubit, and that `cz` and `move` act on the index
of a qubit, then of the resonator, on a pair the table lists as a locus of that gate.

A text that does not fit the table stops the call before the metered job is made, with a stop `prepare`
at the step `table`. The `init_done` line lists each problem in `table_problems`, for example
`cz on indices 1 and 24: the table of the day has no index 24 (its size is 24)`. The order stays unsent. A
resume with `--max-order` tries again, on the table of that day.

When the table cannot be read, the call prints a `NOTE`, the `init_done` line holds `table_note` with the
reason, and the job goes with no check. The check also reads only a text with one quantum register, in
plain statements; `table_note` says when the text was not checked.

The `init_done` line holds `table`: `size` (the number of components), `resonators` (the index of each)
and `sha256`, the SHA-256 in hex of this UTF-8 text, with the names of the table:

```text
{"index":{NAME:INDEX,...},"loci":{"cz":[[QUBIT,RESONATOR],...],"move":[[QUBIT,RESONATOR],...]},"qubits":[NAME,...],"resonators":[NAME,...]}
```

It is Python's `json.dumps` with `sort_keys=True` and `separators=(",", ":")`. Each list is sorted; a locus
is the two names in the order of the table, once for all implementations of the gate. The digest changes
when another component sits at an index. No name of a component goes into the record.

## The status file

Each read of the machine starts with the public status file `https://quantum.heappe.it4i.cz/vlq-status.json`,
the address on IT4I's Calibration and Health page. It needs no login, and gets no token. Its four flags
are the rows of that page, UP or DOWN: QPU (`QPU_status`), QCCSW (`QCCW_status`), Internal Scheduler
(`queue_available`) and Overall (`total_status`). The read and the `read` line hold `status`: `flags`
(`null` for one not given), the `timestamp` of the file, and `error` when it cannot be read, else `null`.

The rule `site_status` ({doc}`rules`) stops the call before its first job when a flag is `false`, with exit
code 2 and a reason such as `the VLQ status file shows QPU down`. A file that cannot be read, or a flag that
is not `true` or `false`, passes with a `NOTE`: it never stops a call by itself.

## Results and times

- The service returns pickles. The app reads them with a reader that maps every name to an inert stub, so
  nothing in them is imported or run. It refuses files above a size limit, and has caps on its walk.
- Each `result` line holds `calibration_set`: the id of the calibration set the job ran on, as the
  canonical text of a UUID (lower case, with hyphens), from the fields `calibration_set_id` in
  `results.pkl`. It is `null` when the file gives no id, or two different ids; the result is kept. Jobs
  run on the set `default` unless another is named when the backend is made, and a set can be read by its
  id at <https://extranet.it4i.cz/vlq-calibration/> (IT4I's Calibration and Health page). The app names no
  set. When a new set is made is not published.
- A result needs the counts in `results.pkl` and the key `remote_hw_runtime` of `job.pkl`, the device
  seconds. A value of it that is not a finite number of 0 or more is kept as `null`. With no counts, no
  `remote_hw_runtime` at all, or a file that cannot be read, the call stops at `result_error` and the order
  stays open. When two calls 10 minutes or more apart got that stop,
  `qdevices resolve RECORD ORDER --unreadable` makes the order final, counted at `job_seconds_limit`. A
  download that gets no usable answer (a redirect or an HTTP error of 400 or more, or no answer up to
  `wait_seconds`) also stops at `result_error`; then the two calls must be 24 hours or more apart
  ({ref}`resolving`).
- HEAppE gives `StartTime` and `EndTime` with no zone, and does not publish its zone. They appear to be
  local time: in the release gate, in summer time, they were two hours ahead of UTC. The `node_seconds` of
  an init job are `EndTime` minus `StartTime`, so they may be one hour off across a change of the clocks.
  A time below zero is no measure: it is written as `null` and left out of the sum of `usage`.

## Traps

- A job that was created and not submitted is left as it is. SubmitJob is never called on a resume, and
  the record decides what becomes of a job that HEAppE shows as Configuring ({doc}`live-runs`).
- An HTTP 4xx other than 401, 403, 408 and 429 to the upload of the circuit file is a refusal: the job was
  made and is never submitted, and the order is final. Any other failed request of the metered job is
  unknown ({doc}`live-runs`).

**Sources:** {doc}`references`

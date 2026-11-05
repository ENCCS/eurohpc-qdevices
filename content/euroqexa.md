# Euro-Q-Exa (LRZ)

**Official pages**

- [Munich Quantum Portal](https://portal.quantum.lrz.de): tokens, jobs and device status
- [LRZ: General information on the Euro-Q-Exa user operation](https://doku.lrz.de/general-information-on-the-euro-q-exa-user-operation-2985665099.html)
- [LRZ: Euro-Q-Exa regular user operation](https://doku.lrz.de/euro-q-exa-regular-user-operation-2985665098.html)
- [LRZ: HPCQC System Access and HPCQC Job Submission via MQSS-Adapter](https://doku.lrz.de/documentation-hpcqc-system-access-and-hpcqc-job-submission-via-mqss-adapter-2603423874.html) (the HPC route, which the app does not use)
- [MQSS Interfaces Documentation](https://munich-quantum-software-stack.github.io/MQSS-Interfaces/), with the MQSS adapter guide
- Support: the LRZ Servicedesk, service "Consulting Quantum Computing", <https://servicedesk.lrz.de/en/simplesubmit/164>

To get an account and a first job: the lesson page
[A few details on Euro-Q-Exa](https://enccs.github.io/eurohpc-quantum-devices-access-hpcqc/euro-q-exa/).

| | |
|---|---|
| Access | the REST interface of the Munich Quantum Portal, `https://portal.quantum.lrz.de:4000/v1` |
| Token | make one on the Tokens page of the portal, and set `MQSS_TOKEN`. The [demo slides of the Euro-Q-Exa kick-off](https://portal.quantum.lrz.de/documents/Euro-Q-Exa-Demo.pdf) show this step |
| Manifest | `"machine": "EQE1"`; one OpenQASM circuit per job, sent unchanged as a list of one text, the form the public reference clients send. A file with more than one `OPENQASM` line fails the checks: a file to send holds one job |
| Limits | 3,000,000 shots times gates a job (below). The public portal code has two active jobs per user and resource, and 24 hours for a job sent with `queued` true while the machine is offline. The app sends one job at a time with `queued` false; the MQSS adapter guide says that such a job is cancelled when the machine is offline. The app reads the machine only before the first job of a call, so a later job sent while it is offline ends as a failed job, and the run stops unless your `on_refusal` rule lets it go on ({doc}`rules`) |
| Billing | wall-clock QPU seconds (LRZ); the records hold the app's own measure ({doc}`billing-and-usage`) |
| Status | LRZ puts each user on a mailing list for notices on the system; users cannot send to it. The Resources section of the portal shows the device status, for example online or maintenance (portal FAQ) |
| Calibration | usually daily, at night, about 1.5 hours, at times several hours, and it can affect running jobs ([LRZ](https://www.lrz.de/en/research/research-projects/detail/calibration-of-quantum-computing)). A way to see the last one is under development (portal FAQ). LRZ's page Euro-Q-Exa regular user operation announces an upgrade that offers 150 qubits |

## Compiling and `no_modify`

Without `no_modify`, the MQSS pipeline of the site compiles and optimises the circuit (portal FAQ). The
record does not hold the compiled circuit: the job page of the portal shows it under Executed Circuit, and
the logs of a failed job in its Note field (portal FAQ).

`"no_modify": true` asks the site not to compile. The circuit must then be in the native gates (`r`, `cz`,
measure, barrier) and on coupled pairs. The dry run checks the gate names against a saved read
(`qdevices check euroqexa --live --manifest FILE`). The LRZ training material of the pilot phase compiles a
circuit locally for `EQE1`, with a chosen qubit layout, and sends it with `no_modify` (its example 03). The
MQSS adapter guide notes: "The transpilation at user end may not be supported for some backends."

**Pairs.** With `no_modify`, the dry run and a live call check each two-qubit gate against the `cz` loci of
the read. A pair listed in neither order fails, and nothing is sent. A pair listed only the other way round
is a note. A note also says when the check was not made: for a text it cannot read (for example several
quantum registers, a range of qubits, or physical qubits), or a read with no readable `cz` loci.

**Layout.** The pairs of the read are the layout ({ref}`layout-pin`). When the layout differs from the pin,
a live call stops before its first job (a stop `check`, with the qubits and pairs then and now). Without
the pin there is no such check; the `read` line still holds the layout.

## Shots times gates

A job may hold at most 3,000,000 shots times gates, summed over the circuits of a batch (LRZ). The app
sends one circuit a job, and counts the gates in the text it sends:

| Statement | Counts |
|---|---|
| each application of a gate, measure, reset | once |
| a statement on whole registers, such as `h q;` or `measure q -> c;` | once for each qubit of the register |
| a call of a gate that the text defines (`gate NAME ... { ... }`) | the operations of its body, calls in it in turn, 32 deep at most |
| a statement under `if (...)` | as above, 32 deep at most |
| barrier, declarations, includes, `qreg`, `creg` | not at all |

The dry run gives the gates and the shots times gates of each job, and fails a job above the limit. Before
each job the rule `shots_times_gates` checks the same: above the limit it stops the call with exit code 2,
and nothing is sent for that job ({doc}`rules`). A job at the limit goes. Above it, use fewer shots or a
shorter circuit; a record that has sent jobs cannot go on with a changed manifest (`send` on {doc}`commands`).

Some texts cannot be counted: for example a modifier such as `ctrl @`, `delay`, a physical qubit such as
`$0`, a range of qubits, nesting deeper than 32, or a gate that calls itself. The dry run then shows
`gates not counted` with a note, and the rule passes with a note: check the job yourself against
3,000,000. Without `no_modify` the site's count can be higher than the app's; the dry run notes it.

## Times

The site writes `timestamp_submitted`, `timestamp_scheduled` and `timestamp_completed` with no zone. They
appear to be local time in Germany (two hours ahead of UTC in summer, in the release gate). The app reads
them as UTC+2 from 01:00 UTC on the last Sunday of March to 01:00 UTC on the last Sunday of October, and
UTC+1 at any other time; in the hour that the October change repeats, it takes the reading nearest its own
time of the job request. The result line keeps the stamps, and adds `scheduled_utc`, `completed_utc` and
`zone_check`. With `zone_check` `true`, the seconds run from `scheduled_utc` to `completed_utc`. It is
`false` when the record has neither time for the job, `timestamp_submitted` is more than 5 minutes from it,
or a stamp cannot be read so or has two readings: the seconds are then the plain difference of the stamps,
and could be one hour off. A difference below zero is no time: the seconds are then `null`, and the result
counts as one with no `seconds` ({doc}`billing-and-usage`).

## Traps

- An answer of HTTP 400 or 422 to the job request is a refusal only when its body has a word that starts
  with `cz`, `pair`, `coupler`, `direction`, `locus`, `loci`, `qubit`, `no_modify`, `gate` or `native`
  and ends there or with an `s`, in upper or lower case: `gates` is such a word, `gateway` is not. Any
  other answer with no job id, or no answer, is unknown ({doc}`live-runs`).
- A 403 is not always a fault of the token. In the release gate a token that worked before and after got a
  403 while the portal login failed with Internal Server Error; the cause is not known. Check the portal
  login before you make a new token.
- In the release gate a Bell job in `h` and `cx`, sent for the site to compile, stayed WAITING for days
  while the machine was online with no job pending; the cause is not known. It came back after four days,
  never cancelled, with 100 of 100 shots and 342,011.9 s from scheduled to completed: not device time
  (inferred). The rule `job_time` stopped the order. Such a result counts at `job_seconds_limit` after
  `qdevices resolve RECORD ORDER --over-limit` ({doc}`billing-and-usage`). `euroqexa-one-qubit` is also
  sent for the site to compile.

**Sources:** {doc}`references`

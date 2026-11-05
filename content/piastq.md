# Piast-Q (PCSS)

**Official pages**

- [PCSS: Piast-Q](https://quantum.psnc.pl/en/piast-q/)
- [PCSS: PIAST-Q, with the specification list](https://www.pcss.pl/en/piast-q/)
- [PCSS broker: the list of machines](https://api.quantum.psnc.pl/api/open/machines), which needs no key
- [PCSS Slurm plugin: Troubleshooting](https://gitlab.pcss.pl/quantum/psnc-sdk/slurm-hpc-plugin/-/raw/main/doc/troubleshooting.md)
- [PyPI: pcss-qapi, the PCSS client](https://pypi.org/pypi/pcss-qapi/json) (the record of its releases)
- Support: [PCSS: Contact](https://quantum.psnc.pl/en/kontakt/)

To get an account and a first job: the lesson page
[A few details on Piast-Q](https://enccs.github.io/eurohpc-quantum-devices-access-hpcqc/piast-q/).

| | |
|---|---|
| Access | the PCSS broker at `https://api.quantum.psnc.pl/api/open`, with the key in the header `X-API-Key`. The app talks to the broker of the PCSS client `pcss-qapi` 0.2.2; its releases 0.3.0 and 0.3.1 talk to another service. No public page says how long the broker stays in service |
| Token | the API key that PCSS issues for the broker, in `PCSS_API_KEY`. No public page says how it is issued |
| Manifest | `"machine": "AQT"`, the machine name in the broker |
| Billing | no public rule and no device time: the records hold wall seconds ({doc}`billing-and-usage`) |
| Send hours | no default. If you are given hours to send in, set `window` and `window_zone` ({doc}`configuration`): a job is then sent only inside a window. When the rule `window` stops a call, resume inside a window |

## The job file

Each job file is a JSON object with the operation list of the broker:

```json
{"number_of_qubits": 2, "quantum_circuit": [{"operation": "RXX", "qubits": [0, 1], "theta": 0.5},
                                            {"operation": "MEASURE"}]}
```

- Angles are in units of pi: `R` takes theta in [0, 1] and phi in [0, 2], `RXX` theta in [0, 0.5], `RZ`
  any phi. The list ends with one `MEASURE`. The broker refuses a value outside its schema with HTTP 422;
  the dry run checks the same ranges offline.
- The dry run also checks 1 to 20 qubits, the 20 data qubits of the PIAST-Q specification of PCSS, and 1
  to 2000 operations, the limit of a circuit in the maker's [AQT Public API 1.1.1](https://arnica.aqt.eu/api/v1/docs).
- By that interface, the maker's machines rewrite an `R` with theta at most pi/5 (0.2 here) as two
  rotations; whether Piast-Q does is not published.

## Shots

**Keep 200 shots a job**, the limit the app holds, unless PCSS says otherwise.

- No public PCSS page gives a limit. Release 1.15.0 of the maker's client library caps a job on a machine
  at a customer's site at 200 shots (a later pre-release allows 2000). LRZ gives 200 for its own machine of
  this maker ([knowledge base for users of the AQT system](https://doku.lrz.de/knowledge-base-for-users-of-the-aqt-system-1620872799.html)).
- The broker does not check the shots. A job above the limit is not refused, and can stay open with no
  answer: in the release gate a Bell job of 400 shots stayed New for four days. It blocked a new run until
  it was resolved as still New with `qdevices resolve ... --none` ({ref}`resolving`); the same circuit at
  200 shots then ran in 182.8 s.
- Set `site_max_shots` only when PCSS gives your award another limit in writing ({doc}`configuration`).
  The dry run notes a value above 200.

## The broker

- **Machine list.** `GET /machines` gives the names only, with no state; the app does not read the queue
  count (`GET /machines/queue-count`). So "online", in `qdevices check piastq --live` and the rule
  `machine`, means only that the name is in the list ({doc}`rules`). The qubits of the read are the 20 that
  the app holds, not a read of the machine.
- **Connections.** The troubleshooting text names the answer HTTP 429 `max connections reached`, with no
  number. The app keeps one connection in use. A 422 with an upstream 429 in the detail is not a refusal:
  a job request that gets it leaves a lost order, and a read of the state or result that gets it is a
  missed poll ({doc}`live-runs`).
- **Results.** How long the broker keeps a result is not published: collect each job the same day. The
  answer code 4 with `Unknown job. May be expired.`, whatever the HTTP status, ends the call with a stop
  `result_expired`. The order stays open (exit code 1). Resume once more, 10 minutes or more later. When
  two calls got that answer, `qdevices resolve RECORD ORDER --expired` makes the order final: never sent
  again, counted at `job_seconds_limit` ({ref}`resolving`). A result that is not a list of shots, each a
  list of bits, ends the call with a stop `result_error`, and the order stays open; when two calls 10
  minutes or more apart got it, `--unreadable` makes the order final, counted the same way. A read of the
  result with no usable answer (a redirect or an HTTP error of 400 or more, or no answer or too many
  connections up to `wait_seconds`) also stops at `result_error`; then the two calls must be 24 hours or
  more apart.
- **A lost order.** The broker has no published call that lists your tasks (PCSS client 0.2.2). Ask PCSS
  whether a task was made. Then give its id with `qdevices resolve RECORD ORDER --job ID`, or `--none`
  only when PCSS says none was made.

**Sources:** {doc}`references`

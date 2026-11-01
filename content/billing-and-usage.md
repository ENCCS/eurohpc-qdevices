# Billing and usage

Set `budget_seconds` with this page in mind. The app shows the rule of each site, where there is one, and
the seconds that the records hold. It does not claim what a site bills: the accounting of the site
decides what your award was charged. What "QPU hours" mean at each site: the lesson page
["QPU hours" on the devices](https://enccs.github.io/eurohpc-quantum-devices-access-hpcqc/qpu-hours/).

| Site | Rule of the site | What the records hold |
|---|---|---|
| VLQ | `max(shots x 400 us, 0.9 s)` per job, the worst case of the [IT4I consumption guide](https://docs.it4i.cz/en/docs/clusters/vlq/vlq-consumption-guide); for a typical circuit a shot costs about 350 us plus the time of the circuit. Each job also has 3 to 15 s of latency, which IT4I does not bill. Init jobs book classical node time only | the device seconds the job reports, which can be below the 0.9 s floor; `runs` and `usage` show both |
| Euro-Q-Exa | EuroHPC time is billed in wall-clock QPU seconds, not in [equivalent qubit-seconds](https://doku.lrz.de/definition-of-the-computing-unit-for-the-lrz-quantum-systems-1898715012.html), a unit LRZ also defines (LRZ) | the seconds from scheduled to completed, the app's own measure |
| Piast-Q | no public rule | wall seconds, from the submission to the result, as Piast-Q gives no device time |

The dry run prints the cost of each job by the published rule, and the rule of the site in its `billing`
line.

## The budget

Before each job the rule `budget` adds up:

- the measured seconds of every result in every record of the site and project, and in `older_records`
  (a negative time counts 0);
- `job_seconds_limit` for each order of unknown time: a lost or open order, a failed job, an order with
  no result that an older runner wrote as `expired`, and a result with no measured seconds;
- `job_seconds_limit` for the job about to be sent.

Above `budget_seconds`, the job is not sent and the run stops. Raise `budget_seconds` only if your award
allows it. The sum is an upper bound of what the app has used, not the charge of the site.

- **Measured seconds** are the first number among `seconds`, `device_seconds` (older runners) and
  `wall_seconds`. `wall_seconds` (job request to result) is a number when the call that sent the job also
  collected it, else null. So a result with no `seconds` (for example a Euro-Q-Exa result whose time stamps
  cannot be read) counts its wall seconds, or else `job_seconds_limit`. `jobs`, `runs` and `usage` show
  them as measured, and `resolve --over-limit` judges on them. The rule `job_time` reads `seconds` only,
  so it stops at such a result.
- **0 seconds:** a refusal, a job never submitted, and an order resolved with `--none`. But an order
  resolved as still `New`, or one whose job id no URL can hold, counts at `job_seconds_limit`: its job may
  yet run.
- **After `--over-limit`, `--expired` or `--gone`:** the `counted_seconds` of the `resolved` line, the
  `job_seconds_limit` of the config at the decision. A later change of the config does not change them.
  For a record of another runner, a result it writes later counts with its measured seconds
  ({ref}`resolving`).
- **Other members:** the app counts only the records it reads. LRZ counts the use of every member of a
  project against one budget
  ([General information on the Euro-Q-Exa user operation](https://doku.lrz.de/general-information-on-the-euro-q-exa-user-operation-2985665099.html)).
  Set `budget_seconds` with the use of the other members in mind.

## A result above the job time limit

The seconds the site reports can hold a wait at the site, cause not known. On Piast-Q, a result collected
by a later call holds the wall seconds up to that call. The rule `job_time` then stops the run, and the
result counts with all its seconds, so the rule `budget` can stop every later send of the project.

When you find that the time is such a wait, give `qdevices resolve RECORD ORDER --over-limit`. The result
then counts at `job_seconds_limit`; its measured seconds stay in the record, and `runs` and `usage` show
both. Decide it for each order: a job that did run that long would then count too little.

## `qdevices usage`

`qdevices usage [PATH ...]` gives the totals by site and project ({doc}`commands`). Seconds counted put the
seconds of a decision of `--over-limit`, `--expired` or `--gone` in place of the measured ones. Neither is
the sum of the budget: both leave out each order of unknown time, and an order resolved as still `New`.
The totals come from the records found, not from the sites. To count older records, give their folders as
`PATH`, or list them in `older_records`.

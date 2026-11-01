# Configuration

Put your projects and limits in `~/.config/qdevices/qdevices.toml`; start from `examples/qdevices.toml`
(below). It has one table per site: `[euroqexa]`, `[vlq]` and `[piastq]`. An unknown table or key is
refused, so that no secret goes there by mistake. **No token goes in this file.** Without the file no
project is allowed: a dry run reports it, and a send is refused.

| Key, every site | Type | Default | What it does |
|---|---|---|---|
| `projects` | list of texts | none | the projects a manifest may name; a send for another project is refused |
| `budget_seconds` | number | none | **needed to send**: the seconds the app may use on the site, summed over all records of the site and project ({doc}`billing-and-usage`). 0 or more; 0 stops every send, and the other commands still work |
| `job_seconds_limit` | number | 300 | above 0: the most time one job may take; the budget counts an order of unknown time at this value |
| `wait_seconds` | number | 900 | the longest wait for one job; then the call ends, the job stays open, and a resume collects it. On VLQ a longer wait needs more time left on the token (the rule `token`, {doc}`rules`) |
| `award_hours` | number | none | the hours of your award, shown by `qdevices usage` |
| `max_shots` | whole number | none | 1 or more: your own limit on the shots of one job, below the limit of the site |
| `older_records` | list of texts | none | folders or records of other runners under the same award; they count in the budget and the open-order check of a send to their site, and the app never writes them ({doc}`manifests-and-records`) |

| Site | Key | What it does |
|---|---|---|
| VLQ | `lexis_projects` | the LEXIS projects the device time may be booked on; the `lexis_project` of a VLQ manifest must be listed. No flag changes it |
| Piast-Q | `window` | the hours a job may be sent in, as `"Mon 09:00-12:00"` or `"Wed-Thu 14:00-18:00"`; outside them no job is sent. A window does not wrap: give Fri-Sun and Mon as two windows, and the hours within one day |
| Piast-Q | `window_zone` | the time zone of `window`, for example `"Europe/Warsaw"`; the default is `"UTC"` |
| Piast-Q | `site_max_shots` | 1 or more: replaces the limit of 200 shots a job that the app holds for Piast-Q; set it only on the site's written word ({doc}`piastq`) |

A lower value of `max_shots`, `site_max_shots` or `job_seconds_limit` would turn their rule off, so it is
refused. Euro-Q-Exa has no key of its own: the app holds its limit of 3,000,000 shots times gates a job
(LRZ), and no key changes it ({doc}`euroqexa`).

- Set `budget_seconds` well below the award. A lost or open order counts at `job_seconds_limit`, so a small
  `job_seconds_limit` leaves more of the budget usable.
- Set `job_seconds_limit` above the longest job you expect: a longer result stops the run (the rule
  `job_time`).
- Set `wait_seconds` to what you are willing to wait in one call.

```{literalinclude} ../examples/qdevices.toml
:language: toml
```

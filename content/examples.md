# Examples

Check an example with `qdevices dry-run examples/FOLDER/manifest.json`: no network call, no token. Put
your own project in the manifest and in `qdevices.toml` in place of the placeholders. Then follow the steps
of {doc}`installing`; they work for every folder. `examples/` also holds an example config (`qdevices.toml`)
and rules file (`rules_bell.py`, {doc}`rules`).

| Folder | Site | What it sends | What a perfect machine would give |
|---|---|---|---|
| `euroqexa-one-qubit` | Euro-Q-Exa | an X gate on one qubit, 100 shots | `1` every time |
| `euroqexa-bell` | Euro-Q-Exa | a Bell pair (H, CX), 100 shots | `00` and `11`, about half each |
| `euroqexa-three-jobs` | Euro-Q-Exa | the two above, and the Bell job again: send the first order alone, look at it, then go on | as above |
| `vlq-one-qubit` | VLQ | a PRX rotation by pi on one qubit, 100 shots | `1` every time |
| `vlq-bell` | VLQ | a Bell pair in native gates, through the resonator | `00` and `11` |
| `piastq-one-qubit` | Piast-Q | an R rotation by pi, 100 shots | `1` every time |
| `piastq-bell` | Piast-Q | one RXX gate at its largest angle, 100 shots | `00` and `11` |

- A real machine has noise, so the counts spread.
- VLQ does not compile: the indices of a VLQ text must match the table of the day ({doc}`vlq`).
- In the release gate, the circuits of `vlq-one-qubit`, `piastq-one-qubit`, `euroqexa-bell` and
  `piastq-bell` (at 400 shots, then at 200) were sent with this app. The one-qubit jobs came back the same
  day; {doc}`euroqexa` and {doc}`piastq` say what became of the Bell jobs. `euroqexa-one-qubit`,
  `euroqexa-three-jobs` and `vlq-bell` have not run on hardware with this app.
- `examples/qrisp/` has a Bell pair, a GHZ state and a QFT for Euro-Q-Exa, written with Qrisp ({doc}`qrisp`).

## Starter examples from the sites' own material

These four take their circuit from a manual or tutorial of the site or of the machine's maker, written
again in the form the app sends. Each manifest names its source in the key `source`, which the record
copies to its start line. None of them has run on hardware with this app.

| Folder | What it sends | What a perfect machine would give | Source, and its licence |
|---|---|---|---|
| `euroqexa-ghz` | a GHZ state on three qubits (H, CX, CX), 100 shots | `000` and `111`, about half each | LRZ training material of the pilot phase, `examples/04_reading_from_qasm.py` ([Training-Material](https://github.com/Munich-Quantum-Software-Stack/Training-Material), commit `fa35d0e`); no licence stated |
| `euroqexa-inverse` | prepare `011`, apply H and controlled RZ gates, then their inverse, 200 shots | `011` every time (qubits 0 and 1 read 1) | MQSS adapter example `examples/inverse_unitary_test.py` (commit `ea83f4e`), Munich Quantum Software Stack, to which the portal FAQ points; Apache-2.0 |
| `vlq-ghz` | a GHZ state on five qubits in native gates, through the resonator, 1000 shots | `00000` and `11111` | the circuit of the IT4I notebook [GHZ_example.ipynb](https://docs.it4i.cz/en/general/GHZ_example.ipynb) (the site says all rights reserved: only the circuit is taken); the star form of the maker's IQM Academy notebook `DenebGHZ.ipynb` ([iqm-finland/sdk](https://github.com/iqm-finland/sdk/tree/main/iqm_academy_examples/gate/star)); Apache-2.0 |
| `piastq-native` | the three native operations: RZ, R and RXX on two qubits, 100 shots | all four outcomes, about a quarter each | the default example of `POST /submit/{workspace}/{resource}` in the [AQT Public API 1.1.1](https://arnica.aqt.eu/api/v1/docs); no licence stated |

What was changed from each source:

- Euro-Q-Exa: both texts are OpenQASM 2, the form the app sends, and the site compiles them, as the sources
  expect ({doc}`euroqexa`). The GHZ source is OpenQASM 3 with 1000 shots. The inverse-unitary source builds
  its gates in a loop; here they are written out.
- VLQ: the CX gates of the IT4I circuit are in native form. The first qubit moves into the resonator, each
  other qubit takes `r(pi/2, -pi/2)`, `cz` with the resonator and `r(pi/2, pi/2)`, and the first qubit
  moves back. The source runs 5000 shots; 1000 shots cost the same 0.9 s floor by the published rule.
- Piast-Q: the operation list of the API example as it is. The source asks for 5 shots.

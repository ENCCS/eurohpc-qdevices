"""Unit tables of the texts: the light reading of OpenQASM, the token filter, and the billing rule of each site.

QUOTED has a quote in its first 8 characters: its raw and JSON forms start apart, so the filter order does not matter.
"""

import base64
import json

from fakes import QASM, TOKEN

from qdevices import billing
from qdevices.qasm import Qasm
from qdevices.redact import redact, redact_all
from qdevices.sites import SITES

TEXTS = {               # name: OpenQASM text; what each answer of Qasm gives is in the golden
    "one qubit": QASM.decode(),
    "a defined gate and comments": ('OPENQASM 2.0;\ninclude "qelib1.inc";\n// x q[0];\n/* h q[1]; */\n'
                                    "gate bell a, b { h a; cx a, b; }\nqreg q[2];\ncreg c[2];\nbell q[0], q[1];\n"
                                    "measure q -> c;\n"),
    "openqasm 3 with an int": ('OPENQASM 3.0;\ninclude "stdgates.inc";\nint x = 1;\nqubit[2] q;\nbit[2] c;\n'
                               "h q[0];\ncz q[0], q[1];\nc[0] = measure q[0];\nc = measure q;\n"),
    "if, parameters, reset and barrier": ("OPENQASM 2.0;\nqreg q[3];\ncreg c[3];\nrz(pi/4) q[0];\nU(0, 0, 0) q[1];\n"
                                          "if (c == 1) x q[2];\nreset q[0];\nbarrier q;\n"),
    "a whole register": "OPENQASM 2.0;\nqreg q[3];\ncreg c[3];\nh q;\ncx q[0], q[2];\nmeasure q -> c;\n",
    "braces": "OPENQASM 3.0;\nqubit[2] q;\nfor int i in [0:1] { x q[i]; }\n",
    "a range": "OPENQASM 2.0;\nqreg q[3];\nx q[0:2];\n",
    "two registers": "OPENQASM 2.0;\nqreg a[1];\nqreg b[2];\ncx a[0], b[1];\n",
    "a qubit with no size": "OPENQASM 3.0;\nqubit[2] q;\nqubit a;\nx a;\nh q;\n",
    "no register": "OPENQASM 2.0;\n",
}
JWT = "eyJ" + "a" * 20 + "." + "b" * 30 + "." + "c" * 10           # synthetic, in the form of a JWT
B64 = base64.b64encode(b"Q" * 50).decode()                         # synthetic, in the form of an envelope password
PLAIN = "plain-secret-1234"
QUOTED = 'q"uo\\te-secret-5678'
PARTS = [               # joined by " | ": each pattern of the filter, then the two secrets in each form
    f"Bearer {JWT}",
    "fernet gAAAAABfernettext==",
    "envelope Z0FBQUFBbase64form=",
    f"USER_JWT_PWD={B64}",
    f"'USER_JWT_PWD': '{B64}'",
    f'"USER_JWT_PWD": "{B64}"',
    f'{{"Name": "USER_JWT_PWD", "Value": "{B64}"}}',
    f'{{"Value": "{B64}", "Name": "USER_JWT_PWD"}}',
    f'{{\\"Name\\": \\"USER_JWT_PWD\\", \\"Value\\": \\"{B64}\\"}}',
    f"plain {PLAIN} {json.dumps(PLAIN)}",
    f"quoted {QUOTED} {json.dumps(QUOTED)}",
    f"cut {PLAIN[:10]} and {json.dumps(QUOTED)[1:12]}",
]


def test_qasm_on_a_table_of_texts(golden):
    lines = []
    for name, text in TEXTS.items():
        parsed = Qasm.parse(text)
        lines += [f"{name}:\n",
                  f"  declared_gates {sorted(parsed.declared_gates)}\n",
                  f"  qubits {parsed.qubits!r}\n",
                  f"  gate_names {sorted(parsed.gate_names)}\n",
                  f"  register {parsed.register!r}\n",
                  f"  operations {parsed.operations!r}\n",
                  f"  gate_count {parsed.gate_count!r}\n"]
    golden("units_text_qasm", "".join(lines))


def test_the_token_filter_on_each_pattern_and_on_two_secrets_in_each_form(golden):
    out = redact(" | ".join(PARTS), [PLAIN, QUOTED])
    golden("units_text_redact", "".join(f"{part}\n" for part in out.split(" | ")))
    for secret in (JWT, "gAAAAABfernettext", "Z0FBQUFBbase64form", B64, PLAIN[:8], QUOTED[:8],
                   json.dumps(QUOTED)[1:9]):
        assert secret not in out
    assert len(out.split(" | ")) == len(PARTS)


def test_the_filter_of_a_value_takes_out_each_text_and_key_and_keeps_the_rest(golden):
    value = {TOKEN: [TOKEN, ("a", 1)], "n": None, "k": 3.5, 2: {"inner": f"x {TOKEN} y"}}
    golden("units_text_redact_all", f"{redact_all(value, [TOKEN])!r}\n")


def test_the_billing_rule_of_each_site(golden):
    lines = [f"{site} {shots}: {billing.published_seconds(site, shots)!r}\n"
             for site in ("vlq", "euroqexa", "piastq") for shots in (1, 2250, 2251, 10000)]
    lines += [f"rule {site}: {SITES[site].profile.billing.text}\n" for site in ("vlq", "euroqexa", "piastq")]
    lines += [f"award {conf}: {billing.award_seconds(conf)!r}\n" for conf in ({}, {"award_hours": 5},
                                                                                 {"award_hours": 0.5})]
    golden("units_text_billing", "".join(lines))

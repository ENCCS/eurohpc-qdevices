OPENQASM 3.0;
include "stdgates.inc";
gate r(theta, phi) q {
    gphase(0);
}
qubit[1] q;
bit[1] c;
r(pi, 0) q[0];
c[0] = measure q[0];

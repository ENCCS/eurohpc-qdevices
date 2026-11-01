OPENQASM 3.0;
include "stdgates.inc";
gate r(theta, phi) q {
    gphase(0);
}
gate move q0, q1 {
    gphase(0);
}
qubit[25] q;
bit[2] c;
r(pi/2, pi/2) q[0];
r(pi/2, -pi/2) q[1];
move q[0], q[24];
cz q[1], q[24];
move q[0], q[24];
r(pi/2, pi/2) q[1];
c[0] = measure q[0];
c[1] = measure q[1];

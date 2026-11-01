OPENQASM 3.0;
include "stdgates.inc";
gate r(theta, phi) q {
    gphase(0);
}
gate move q0, q1 {
    gphase(0);
}
qubit[25] q;
bit[5] c;
r(pi/2, pi/2) q[0];
move q[0], q[24];
r(pi/2, -pi/2) q[1];
cz q[1], q[24];
r(pi/2, pi/2) q[1];
r(pi/2, -pi/2) q[2];
cz q[2], q[24];
r(pi/2, pi/2) q[2];
r(pi/2, -pi/2) q[3];
cz q[3], q[24];
r(pi/2, pi/2) q[3];
r(pi/2, -pi/2) q[4];
cz q[4], q[24];
r(pi/2, pi/2) q[4];
move q[0], q[24];
c[0] = measure q[0];
c[1] = measure q[1];
c[2] = measure q[2];
c[3] = measure q[3];
c[4] = measure q[4];

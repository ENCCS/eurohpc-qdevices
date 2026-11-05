# References

Check the official pages of the sites for the newest details. The facts of the site pages come from the
pages below. A fact marked with the name of a site alone, such as (LRZ), is the answer of that site on its
own rules. The sources of the starter examples, and their licences, are in {doc}`examples`.

## ENCCS

- The lesson [EuroHPC JU quantum devices and HPC-QC access in practice](https://enccs.github.io/eurohpc-quantum-devices-access-hpcqc/):
  applying, onboarding at each site, and a first job on each machine. Its pages used here:
  [onboarding](https://enccs.github.io/eurohpc-quantum-devices-access-hpcqc/onboarding/), ["QPU hours" on the devices](https://enccs.github.io/eurohpc-quantum-devices-access-hpcqc/qpu-hours/),
  [Euro-Q-Exa](https://enccs.github.io/eurohpc-quantum-devices-access-hpcqc/euro-q-exa/), [VLQ](https://enccs.github.io/eurohpc-quantum-devices-access-hpcqc/vlq/) and [Piast-Q](https://enccs.github.io/eurohpc-quantum-devices-access-hpcqc/piast-q/).
- The lesson's [Official links, by task](https://enccs.github.io/eurohpc-quantum-devices-access-hpcqc/quick-reference/#official-links):
  the official pages, in one table.
- The white paper [Quantum Computing in the EuroHPC JU Ecosystem: A Practical Guide for European SMEs](https://doi.org/10.5281/zenodo.17862354):
  an overview of the EuroHPC quantum computers.

## LRZ, Euro-Q-Exa

- [Munich Quantum Portal](https://portal.quantum.lrz.de)
- [LRZ Servicedesk: Consulting Quantum Computing](https://servicedesk.lrz.de/en/simplesubmit/164)
- [LRZ: General information on the Euro-Q-Exa user operation](https://doku.lrz.de/general-information-on-the-euro-q-exa-user-operation-2985665099.html)
- [LRZ: Euro-Q-Exa regular user operation](https://doku.lrz.de/euro-q-exa-regular-user-operation-2985665098.html)
- [LRZ: Definition of the computing unit for the LRZ Quantum Systems](https://doku.lrz.de/definition-of-the-computing-unit-for-the-lrz-quantum-systems-1898715012.html) (the equivalent qubit-second)
- [LRZ: HPCQC System Access and HPCQC Job Submission via MQSS-Adapter](https://doku.lrz.de/documentation-hpcqc-system-access-and-hpcqc-job-submission-via-mqss-adapter-2603423874.html) (the HPC route, which the app does not use)
- [LRZ: Quantum computing: Using AI for Calibration](https://www.lrz.de/en/research/research-projects/detail/calibration-of-quantum-computing)
- [LRZ: MQSS Interactive Demo, slides of the Euro-Q-Exa kick-off](https://portal.quantum.lrz.de/documents/Euro-Q-Exa-Demo.pdf)
- [Munich Quantum Software Stack: MQP-Dashboard-Frontend](https://github.com/Munich-Quantum-Software-Stack/MQP-Dashboard-Frontend), `src/components/Pages/FAQ/FAQ.js` (the portal FAQ, commit `0e05815`)
- [Munich Quantum Software Stack: MQP-Database-Access](https://github.com/Munich-Quantum-Software-Stack/MQP-Database-Access), `bqp_database_access/jobs.py` (commit `d20ecfd`)
- [Munich Quantum Software Stack: Training-Material](https://github.com/Munich-Quantum-Software-Stack/Training-Material), `README.md` and `examples/03_transpiled_circuit_submission.py` (commit `fa35d0e`)
- [Munich Quantum Software Stack: mqss-client 0.2.1 on PyPI](https://files.pythonhosted.org/packages/78/3f/4a3eb4193e5a7b97b4e1a11177f82a12825e5ff94a8697fd1a43238b1d42/mqss_client-0.2.1.tar.gz), `mqss_client/job.py` and `mqss_client/mqss_client.py`
- [Munich Quantum Software Stack: MQSS Interfaces Documentation](https://munich-quantum-software-stack.github.io/MQSS-Interfaces/) (the MQSS adapter guide, version 0.2.0, is under it)

## IT4Innovations, VLQ

- [IT4Innovations: VLQ access documentation](https://docs.it4i.cz/en/docs/clusters/vlq/access)
- [IT4Innovations: Estimating Consumption on VLQ](https://docs.it4i.cz/en/docs/clusters/vlq/vlq-consumption-guide)
- [IT4Innovations: VLQ Calibration and Health](https://docs.it4i.cz/en/docs/clusters/vlq/calibration_health)
- [IT4Innovations: the VLQ calibration sets, by id](https://extranet.it4i.cz/vlq-calibration/)
- [IT4Innovations: status page](https://status.it4i.cz/status/it4i)
- [IT4Innovations: Help and Support](https://docs.it4i.cz/en/docs/general/support)
- [HEAppE: the interface of the VLQ instance](https://quantum.heappe.it4i.cz/heappe/swagger/V6.3.3/swagger.json)
- [HEAppE documentation: Job Monitoring](https://heappe.it4i.cz/documentation/docs/job-management/job-monitoring) (the job states)
- [HEAppE documentation: Resource Accounting](https://heappe.it4i.cz/documentation/docs/accounting-reporting/accounting) (the node time)
- [HEAppE documentation: QScheduler configuration](https://heappe.it4i.cz/documentation/docs/configuration/qscheduler)
- [IT4Innovations: Quantum as a Service, `client.py`](https://github.com/It4innovations/quantum-as-a-service/blob/789fff1f3edd69e7a965e14a53915c61bd493d0d/src/qaas/client/client.py) (commit `789fff1`, version 0.5.2)
- [IT4Innovations: Quantum as a Service, `backend_service.py`](https://github.com/It4innovations/quantum-as-a-service/blob/789fff1f3edd69e7a965e14a53915c61bd493d0d/src/qaas/iqm_backend/backend_service.py) (commit `789fff1`)
- [IT4Innovations: Quantum as a Service, `backend_env_variables.py`](https://github.com/It4innovations/quantum-as-a-service/blob/789fff1f3edd69e7a965e14a53915c61bd493d0d/src/qaas/iqm_backend/backend_env_variables.py) (commit `789fff1`)
- [IT4Innovations: Quantum as a Service, `backend_scripts`](https://github.com/It4innovations/quantum-as-a-service/tree/789fff1f3edd69e7a965e14a53915c61bd493d0d/backend_scripts) (commit `789fff1`)
- [IT4Innovations: Quantum as a Service, pull request 34](https://github.com/It4innovations/quantum-as-a-service/pull/34) (the plan for version 1.0.0)
- [IQM: CircuitCompilationOptions](https://docs.iqm.tech/iqm-client/api/iqm.iqm_client.models.CircuitCompilationOptions.html) (client 35.0.3)
- [IQM: the job request model of station control](https://raw.githubusercontent.com/iqm-finland/sdk/main/src/4.6.3/iqm-station-control-client/src/iqm/station_control/interface/models/circuit.py) (IQM OS 4.6.3)

## PCSS, Piast-Q

- [PCSS: Piast-Q](https://quantum.psnc.pl/en/piast-q/)
- [PCSS: PIAST-Q, with the specification list](https://www.pcss.pl/en/piast-q/)
- [PCSS: Contact](https://quantum.psnc.pl/en/kontakt/)
- [PyPI: pcss-qapi, the PCSS client (the record of its releases; release 0.2.2 holds the broker's interface, release 0.3.1 that of another service)](https://pypi.org/pypi/pcss-qapi/json)
- [PCSS broker: the list of machines](https://api.quantum.psnc.pl/api/open/machines), which needs no key
- [PCSS Slurm plugin: Troubleshooting](https://gitlab.pcss.pl/quantum/psnc-sdk/slurm-hpc-plugin/-/raw/main/doc/troubleshooting.md)
- [AQT Public API 1.1.1](https://arnica.aqt.eu/api/v1/docs)
- [LRZ: Knowledge base for users of the AQT system](https://doku.lrz.de/knowledge-base-for-users-of-the-aqt-system-1620872799.html)
- The maker's client library, release 1.15.0 and a later pre-release

The broker's interface comes from the PCSS client 0.2.2, the operation list from the AQT Public API 1.1.1,
and what the broker did with the jobs of the app from the release gate.

To cite the app, use `CITATION.cff` in the repository, or the DOI of all its versions,
[10.5281/zenodo.23974192](https://doi.org/10.5281/zenodo.23974192).

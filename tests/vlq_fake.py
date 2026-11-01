"""The classes of a fake VLQ results file: a pickle names this module, so it keeps its name and its digests."""


class Counts(dict):
    pass


class JobRecord:
    def __init__(self, seconds):
        self.remote_hw_runtime = seconds


class Parameters:
    """The parameters of a job, as the metadata of a result holds them."""

    def __init__(self, calibration_set_id, shots=10):
        self.shots, self.calibration_set_id = shots, calibration_set_id


class Experiment:
    """One result: its counts, and its metadata with the parameters of the job."""

    def __init__(self, counts, parameters):
        self.data = {"counts": counts}
        self.metadata = {"parameters": parameters}


class Results:
    """A results file: the results, and metadata of its own."""

    def __init__(self, *experiments):
        self.results, self._metadata = list(experiments), {}

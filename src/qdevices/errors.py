"""The error every command shares."""


class Refused(Exception):
    """A wrong argument or a failed check, before anything was sent; exit code 1. Every refusal derives from it."""

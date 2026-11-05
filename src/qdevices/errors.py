"""The error every command shares, and the words for any error in a refusal, a verdict or a stop line."""


class Refused(Exception):
    """A wrong argument or a failed check, before anything was sent; exit code 1. Every refusal derives from it."""


def described(exc: BaseException) -> str:
    """The kind of an error and its text; when str() of the error raises, the words say its text cannot be read."""
    try:
        return f"{type(exc).__name__}: {exc}"
    except (Exception, SystemExit, GeneratorExit):      # code of a user may make str() raise; an interrupt stays one
        return f"{type(exc).__name__} (its text cannot be read)"

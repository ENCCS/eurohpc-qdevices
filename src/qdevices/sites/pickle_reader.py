"""A restricted reader for VLQ's pickles: every name maps to an inert stub, so nothing is imported or run."""

import functools
import io
import pickle
import uuid
from collections.abc import Iterable
from itertools import islice
from typing import Final, Self

from ..values import is_int

MAX_BYTES = 64 * 1024 * 1024
MAX_NODES: Final = 10_000         # the most parts one walk hands out
_LIST_WIDTH: Final = 64           # the most entries of one list a walk hands out, by default
_DICT_WIDTH: Final = 1024         # the most entries of one dict a walk hands out, by default
ID_TEXT: Final = 64               # the longest text read as an id; its usual forms have at most 45 characters


class PickleRefused(Exception):
    """A pickle that the reader does not read."""


class _Stub:
    def __new__(cls, *args: object, **kwargs: object) -> Self:
        obj = object.__new__(cls)
        obj._args, obj._kwargs, obj._state, obj._items, obj._list = args, kwargs, None, {}, []
        return obj

    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    def __setstate__(self, state: object) -> None:
        self._state = state

    def __setitem__(self, key: object, value: object) -> None:
        self._items[key] = value

    def __getitem__(self, key: object) -> object:
        return self._items[key]

    def append(self, value: object) -> None:
        self._list.append(value)

    def extend(self, values: Iterable[object]) -> None:
        self._list.extend(values)

    def __call__(self, *args: object, **kwargs: object) -> Self:
        made = type(self)()
        made._args, made._kwargs = args, kwargs
        return made

    def __repr__(self) -> str:
        return f"<stub {type(self).__module__}.{type(self).__name__}>"

    @staticmethod
    @functools.cache
    def kind(module: str, name: str, /) -> type:
        """The stub class of one name of a module, made once; by position only, so each pair has one cache key."""
        return type(name, (_Stub,), {"__module__": f"stub:{module}"})


class _Reader(pickle.Unpickler):
    def find_class(self, module: str, name: str) -> type:
        return _Stub.kind(module, name)


def loads(data: bytes) -> object:
    """The object of a pickle, with an inert stub for each class it names. PickleRefused for one that is not read."""
    if not isinstance(data, (bytes, bytearray)):
        raise PickleRefused("not bytes")
    if len(data) > MAX_BYTES:
        raise PickleRefused(f"{len(data)} bytes, above the limit of {MAX_BYTES}")
    try:
        return _Reader(io.BytesIO(data)).load()
    except Exception as exc:          # a malformed pickle is a file that cannot be read
        raise PickleRefused(f"the pickle cannot be read: {type(exc).__name__}") from None


def state_of(obj: object) -> dict:
    """The fields of a part: its state, the "__dict__" in it, or the last item of a state tuple. Always a dict."""
    state = getattr(obj, "_state", None)
    if isinstance(state, dict):
        state = state.get("__dict__", state)
    elif isinstance(state, tuple) and state:
        state = state[-1]
    else:
        state = obj
    return state if isinstance(state, dict) else {}


def items_of(obj: object) -> dict:
    """The items set by key on a stub, as a subclass of dict holds them, in a new dict. Empty for any other part."""
    return dict(getattr(obj, "_items", {}) or {})


class Walk:
    """A bounded walk through a loaded pickle."""

    def __init__(self, list_width: int = _LIST_WIDTH, dict_width: int = _DICT_WIDTH, nodes: int = MAX_NODES) -> None:
        self.list_width, self.dict_width, self.left, self.seen, self.cut = list_width, dict_width, nodes, {}, False

    def due(self, node: object, depth: int) -> bool:
        """True for a part not yet met, or met only deeper, so a shared part is searched from its shallowest place."""
        if self.seen.get(id(node), depth + 1) <= depth:
            return False
        self.seen[id(node)] = depth
        return True

    def _some(self, entries: Iterable[object], size: int, width: int) -> list:
        most = max(min(width, self.left), 0)
        self.cut = self.cut or size > most
        taken = list(islice(entries, most))
        self.left -= len(taken)
        return taken

    def fields(self, node: object) -> list:
        """The (key, value) pairs of a dict, or of the state of a stub."""
        found = node if isinstance(node, dict) else state_of(node)
        return self._some(found.items(), len(found), self.dict_width) if isinstance(found, dict) else []

    def entries(self, node: object) -> list:
        """The entries of a list or a tuple, or of a stub built by append."""
        found = getattr(node, "_list", None) or (node if isinstance(node, (list, tuple)) else [])
        return self._some(found, len(found), self.list_width)


def uuid_text(value: object) -> str | None:
    """The canonical text of an id: a stub of uuid.UUID, or a short text in the form of a UUID. Else None."""
    try:
        if type(value) is _Stub.kind("uuid", "UUID"):
            number = state_of(value).get("int")
            return str(uuid.UUID(int=number)) if is_int(number) else None
        return str(uuid.UUID(value)) if isinstance(value, str) and len(value) <= ID_TEXT else None
    except ValueError:                # an int outside 128 bits, or a text that is not a UUID
        return None

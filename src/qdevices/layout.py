"""The layout of a machine: its qubit count, its coupled pairs and the digest a manifest pins it with."""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Self

from .values import is_int, sha256_hex

if TYPE_CHECKING:
    from .sites.protocol import SiteProtocol

SHA: Final = re.compile(r"[0-9a-f]{64}")
KEYS: Final = ("layout_sha256", "qubits", "pairs")


@dataclass(frozen=True, slots=True)
class Layout:
    """A qubit count and its distinct coupled pairs, each pair low qubit first, in sorted order."""

    qubits: int
    pairs: tuple[tuple[int, int], ...]

    @classmethod
    def of(cls, qubits: int, pairs: Iterable[tuple[int, int]]) -> Self:
        """The layout of a qubit count and its pairs, given in any order and either way round."""
        return cls(qubits, tuple(sorted({(min(a, b), max(a, b)) for a, b in pairs})))

    @property
    def canonical(self) -> str:
        """The canonical text of the layout, which the digest is taken of: the same for any order of the pairs."""
        return f"qubits={self.qubits};pairs=" + ",".join(f"{a}-{b}" for a, b in self.pairs)

    @property
    def fields(self) -> dict:
        """The layout of a read: its digest, its qubit count and its number of distinct pairs."""
        return {"layout_sha256": sha256_hex(self.canonical.encode("utf-8")), "qubits": self.qubits,
                "pairs": len(self.pairs)}


@dataclass(frozen=True, slots=True)
class Pin:
    """The "layout" of a manifest as given, at a site whose read gives a layout; None where there is none."""

    given: object

    @classmethod
    def of(cls, manifest: dict, site: "SiteProtocol | type[SiteProtocol]") -> Self:
        """The pin of a manifest: only a site with layout_pin takes one; elsewhere "layout" is just a fact."""
        return cls(manifest["extra"].get("layout") if site.layout_pin else None)

    @property
    def form_problems(self) -> list[str]:
        """The form of the pin, which needs no read. No pin, no problem."""
        pin = self.given
        if pin is None or (isinstance(pin, dict) and isinstance(pin.get("layout_sha256"), str)
                           and SHA.fullmatch(pin["layout_sha256"])
                           and all(is_int(pin.get(key)) and pin[key] >= 0 for key in ("qubits", "pairs"))):
            return []
        return ['"layout" must be {"layout_sha256": 64 hex digits, "qubits": N, "pairs": N}, as '
                "`qdevices check --live` prints it"]

    def problems(self, read: object) -> list[str]:
        """The pin against a read. No pin, no check."""
        form, pin = self.form_problems, self.given
        if pin is None or form:
            return form
        now = read if isinstance(read, dict) else {}
        if not now.get("layout_sha256"):
            return ["the read gives no layout_sha256, so the layout pin of the manifest cannot be checked"]
        if now["layout_sha256"] == pin["layout_sha256"]:
            return []
        return [f"the layout of the machine is not the one the manifest pins: then {pin['qubits']} qubits and "
                f"{pin['pairs']} pairs (the manifest), now {now.get('qubits')} qubits and {now.get('pairs')} pairs "
                "(the read)"]

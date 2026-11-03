"""A dry run of one manifest. It writes nothing, and it needs no config of your own for an example."""

import sys
from pathlib import Path
from typing import Final

from qdevices import config
from qdevices.config import ConfigError
from qdevices.dryrun import dry_run
from qdevices.paths import Places

EXAMPLE: Final = Path(__file__).resolve().parent.parent / "qdevices.toml"


def config_for(manifest: Path, own: Path) -> Path:
    """Your config for a manifest with your names; examples/qdevices.toml for one that holds a placeholder."""
    return EXAMPLE if '"MY-' in manifest.read_text(encoding="utf-8") or not own.exists() else own


def main(argv: list[str]) -> int:
    """The exit code of the dry run of the manifest given."""
    manifest, places = Path(argv[0]), Places.default()
    chosen = config_for(manifest, places.config)
    if chosen == EXAMPLE:
        print("This dry run uses examples/qdevices.toml.")
    try:
        return dry_run(manifest, cfg=config.load(chosen), places=places)
    except ConfigError as exc:
        print(f"REFUSED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

"""`qdevices check`: the token and window of a site, and with --live one read of its machine. It makes no job."""

import json
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass

from . import layout
from . import manifest as manifests
from .clock import Clock, Sleep
from .config import Windows
from .errors import Refused
from .lock import Locks, TakeLock
from .paths import Places
from .redact import redact
from .saved_reads import SavedReads
from .screen import say as default_say
from .sites import SITES
from .sites.base import SiteError


@dataclass(frozen=True, slots=True, kw_only=True)
class _SiteCheck:
    """The check of one site: its lines offline, then, with the token and the lock, one read stored and shown."""

    cls: type
    token: str | None
    site_config: dict
    places: Places
    clock: Clock
    sleep: Sleep
    host: str
    make_site: Callable
    take_lock: TakeLock | None
    say: Callable[[str], None]

    def offline(self) -> int:
        """Whether the token is set, the minutes it has left, and whether the site is inside its window now."""
        cls, token = self.cls, self.token
        self.say(f"{cls.token_env}: {'set' if token else 'not set'} (the token is never printed)")
        label = cls.profile.token_label
        if label and token:
            expiry = cls.profile.token_expiry(token)
            self.say(f"{label}: its expiry cannot be read" if expiry is None else
                     f"{label}: {int((expiry - self.clock.utc().timestamp()) // 60)} minutes left")
        if self.site_config["window"]:
            inside = Windows.of(self.site_config).now(self.clock.utc())
            self.say(f"window {', '.join(self.site_config['window'])} ({self.site_config['window_zone']}): "
                     f"{'inside' if inside else 'outside'} now")
        return 0 if token else 1

    def live(self, manifest_path) -> int:
        """One read of the machine under the lock of the site, stored as a file; 1 when it cannot be read."""
        man, name = self._manifest(manifest_path), self.cls.name
        with (Locks(self.places.state, host=self.host, started=self.clock.utc().isoformat()).held(
                  name, take=self.take_lock),
              closing(self.make_site(man, name, self.token, clock=self.clock, sleep=self.sleep,
                                     site_config=self.site_config)) as site):
            try:
                read = site.read()
            except SiteError as exc:
                self.say(f"FAILED: the machine cannot be read: {redact(str(exc), site.secrets())}")
                return 1
            secrets: list[str] = []

            def read_secrets() -> list[str]:          # read once, last, by the save; then kept for the screen
                secrets.extend(site.secrets())
                return secrets

            file = SavedReads.of(self.places, name).save(read, self.clock, read_secrets)
            self._show(read, file, lambda text: self.say(redact(text, secrets)))
            return 0

    def _manifest(self, manifest_path) -> dict | None:
        cls = self.cls
        if not self.token:
            raise Refused(f"a live check needs the token in {cls.token_env}")
        if manifest_path is not None:
            man = manifests.load(manifest_path, SITES)
            if man["site"] != cls.name:
                raise Refused(f"the manifest is for {man['site']}, not {cls.name}")
            return man
        if cls.profile.route_keys:
            raise Refused(f"a live check of {cls.name} needs --manifest FILE, for the "
                          + " and the ".join(what for _, what in cls.profile.route_keys))
        return None

    def _show(self, read: dict, file, say: Callable[[str], None]) -> None:
        for key in self.cls.profile.read_keys:
            if key in read:
                say(f"  {key}: {read[key]}")
        if read.get("layout_sha256"):
            say('  to pin this layout, add to the manifest:  "layout": '
                     + json.dumps({key: read[key] for key in layout.KEYS}))
        for res, entry in sorted((read.get("resources") or {}).items()):
            say(f"  {res}: {entry.get('qubits')} qubits, online {entry.get('online')}")
        say(f"{'Read' if SavedReads.kind(read) == 'read' else 'List of the machines'} stored in {file}. "
                 "No job was made.")


def check(name: str, *, live: bool, token: str | None, manifest_path, cfg: dict, places, clock: Clock, sleep: Sleep,
          host: str, make_site, take_lock: TakeLock | None = None, say=default_say) -> int:
    """`qdevices check`: the token and window of a site, and with `live` one read of its machine, stored as a file."""
    site_check = _SiteCheck(cls=SITES[name], token=token, site_config=cfg[name], places=places, clock=clock,
                            sleep=sleep, host=host, make_site=make_site, take_lock=take_lock, say=say)
    code = site_check.offline()
    return site_check.live(manifest_path) if live else code

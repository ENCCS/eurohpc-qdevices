"""The base class of every site, the channel of its requests, and the one helper that makes an HTTP client.

No retry, no redirect and no cancel: a job request is never sent twice, and the token goes only to a fixed address.
"""

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final, Self
from urllib.parse import unquote

import httpx

from ..values import ANSWER_DEPTH, in_url, too_deep
from .protocol import Refusal, SiteProtocol

if TYPE_CHECKING:
    from ..clock import Clock, Sleep

BODY_LIMIT: Final = 2000              # the characters of an answer that an error or a log keeps
_ENDS_A_JOB: Final = re.compile(r"cancel|abort|delete", re.IGNORECASE)    # in the path of a request other than GET
_CLIENT_KEYWORDS: Final = frozenset({"auth", "follow_redirects"})         # a client's own settings, never a request's


def cut(value: object) -> str:
    """The text of an answer, cut to its first BODY_LIMIT characters."""
    return str(value)[:BODY_LIMIT]


class SiteError(Exception):
    """An answer of a site that is not a success, or one that cannot be read."""

    def __init__(self, message: str, *, status: int | None = None, body: str | None = None,
                 url: str | None = None, step: str | None = None, busy: bool = False, no_url: bool = False) -> None:
        super().__init__(message)
        self.status, self.body, self.url, self.step, self.busy, self.no_url = status, body, url, step, busy, no_url

    @classmethod
    def _from_reply(cls, response: httpx.Response, method: str, path: str, *, step: str) -> Self:
        """The error of an answer that is not 2xx: its status, its text cut, its url and the step."""
        return cls(f"HTTP {response.status_code} to {method} {path}", status=response.status_code,
                   body=cut(response.text), url=str(response.request.url), step=step)

    def status_at(self, step: str) -> int | None:
        """The HTTP status of this error at this step, or None at another step or with no status."""
        return self.status if self.step == step and isinstance(self.status, int) else None

    @property
    def missed(self) -> str | None:
        """The kind of a failed read that is a missed poll, or None for one that ends the wait."""
        if self.busy:
            return "busy"
        return f"HTTP {self.status}" if isinstance(self.status, int) and self.status >= 500 else None


class NoAnswer(SiteError):
    """No answer was read: a job may or may not exist."""

    @property
    def missed(self) -> str | None:
        """The kind "no answer": a read that got no answer is a missed poll."""
        return "no answer"


class Expired(SiteError):
    """The site answered that it does not know a job it was given: its result may be gone. The order stays open."""

    @property
    def missed(self) -> str | None:
        """None: the answer that the site does not know the job ends the wait."""
        return None


class UnsafeRequest(Exception):
    """A request the app never sends, refused before the transport sees it: an error of the program, not an answer."""


def http_client(base_url: str, headers: dict, *, timeout: float, transport: httpx.BaseTransport | None = None,
                max_connections: int | None = None) -> httpx.Client:
    """The only HTTP client of the app. Tests pass an `httpx.MockTransport`; the address stays fixed."""
    if transport is None:
        limits = httpx.Limits(max_connections=max_connections, max_keepalive_connections=max_connections)
        transport = httpx.HTTPTransport(retries=0, limits=limits)
    return httpx.Client(base_url=base_url, headers=headers, timeout=timeout, follow_redirects=False,
                        transport=transport)


@dataclass(frozen=True, slots=True)
class Channel:
    """The requests to one fixed address of a site, each with its step, which the error of a failure names."""

    client: httpx.Client

    def _unsafe(self, method: str, path: str, kwargs: dict) -> str | None:
        if not isinstance(method, str):          # first: b"DELETE" would pass the checks below, and httpx sends it
            return "its method is not text"
        if httpx.URL(path).is_absolute_url:
            return "an absolute URL would leave the fixed address of the client"
        given = sorted(_CLIENT_KEYWORDS.intersection(kwargs))
        if given:
            return f"the keyword {given[0]} belongs to the client, never to one request"
        if method.upper() == "DELETE" or (method.upper() != "GET" and _ENDS_A_JOB.search(path)):
            return "it could end a job, and the app cancels none"
        return self._unsafe_in_form(method, path, kwargs)     # after the checks above, so their refusals come first

    def _unsafe_in_form(self, method: str, path: str, kwargs: dict) -> str | None:
        token = self.client.headers.get("authorization")
        if httpx.Headers(kwargs.get("headers") or {}).get("authorization", token) != token:
            return "the token goes only in the headers of the client"
        if method.upper() != "GET" and self._ends_a_job(path, kwargs.get("params")):
            return "it could end a job, and the app cancels none"
        return None

    def _ends_a_job(self, path: str, params: object) -> bool:
        text = self.client.build_request("GET", path, params=params).url.raw_path.decode("ascii")
        while (plain := unquote(text)) != text:      # each percent escape undone, as a site may read it
            text = plain
        return _ENDS_A_JOB.search(text) is not None

    def request(self, method: str, path: str, *, step: str, **kwargs: Any) -> httpx.Response:
        """One request, if it is safe. Any answer that is not 2xx, a 3xx among them, is a SiteError."""
        try:
            if unsafe := self._unsafe(method, path, kwargs):
                raise UnsafeRequest(f"{method} {path} is never sent: {unsafe}")
            response = self.client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise NoAnswer(f"no answer to {method} {path}: {type(exc).__name__}", step=step) from None
        except (httpx.InvalidURL, UnicodeEncodeError) as exc:     # a job id no URL holds: nothing is sent
            raise SiteError(f"the request cannot be made: {exc}", step=step) from None
        if not 200 <= response.status_code < 300:
            raise SiteError._from_reply(response, method, path, step=step)
        return response

    def answer(self, method: str, path: str, *, step: str, fields: bool = False, **kwargs: Any) -> Any:
        """The JSON of the answer to one request; with `fields`, an object or empty. Any other answer is a SiteError."""
        response = self.request(method, path, step=step, **kwargs)
        try:
            reply = response.json()
            wrong = (f"JSON of at most {ANSWER_DEPTH} levels" if too_deep(reply)     # the code after it recurses
                     else "a JSON object" if fields and reply and not isinstance(reply, dict) else None)
        except (ValueError, RecursionError):          # RecursionError: nested deeper than the parser goes
            wrong = "JSON"
        if wrong:
            raise SiteError(f"the answer is not {wrong}", status=response.status_code, body=cut(response.text),
                            step=step)
        return reply


class Site(SiteProtocol):
    """The base of each site class: its token, clients and refusal; abstract until it gives its five steps."""

    default_machine: str | None = None
    refusal: Refusal | None = None    # None: no answer is a refusal, so a failed job request leaves the order unknown

    def __init__(self, token: str, machine: str | None = None, *, transport: httpx.BaseTransport | None = None) -> None:
        self._token, self.machine = token, machine or self.default_machine
        self._transport = transport       # of every client of the site; tests give an httpx.MockTransport
        self._clients: list[httpx.Client] = []

    @classmethod
    def from_manifest(cls, manifest: dict, token: str, *, clock: "Clock", sleep: "Sleep", site_config: dict,
                      transport: httpx.BaseTransport | None = None) -> Self:
        """A site for a manifest, made with no request. This default takes its machine only; VLQ takes more."""
        return cls(token, manifest.get("machine"), transport=transport)

    def client(self, address: str, headers: dict, *, timeout: float, max_connections: int | None = None) -> Channel:
        """A channel to one fixed address of this site, over its transport; its client is closed with the site."""
        made = http_client(address, headers, timeout=timeout, transport=self._transport,
                           max_connections=max_connections)
        self._clients.append(made)
        return Channel(made)

    @staticmethod
    def text_of(job: dict) -> str:
        """The text of the file of a job, read as UTF-8, with a replacement for each byte that is not."""
        return job["text"].decode("utf-8", "replace")

    @staticmethod
    def submit_for_id(channel: Channel, path: str, body: dict, *, key: str, what: str) -> str:
        """The one job request of a site that makes and runs a job in one POST. The answer is its id."""
        reply = channel.answer("POST", path, step="submit", json=body)
        found = reply.get(key) if isinstance(reply, dict) else None
        if not found or not in_url(str(found)):         # lost; with an id no URL holds, a job may exist
            raise SiteError(f"the answer to the {what} request has no {key}{' that a URL can hold' if found else ''}",
                            body=cut(reply), step="submit", no_url=bool(found))
        return str(found)

    def classify(self, error: Exception) -> str:
        """By the refusal of the site: "refused" (no job ran, the order is final) or "unknown" (a job may exist)."""
        if self.refusal is None or not isinstance(error, SiteError):
            return "unknown"
        return self.refusal.classify(error)

    def secrets(self) -> list[str]:
        """The token, which the token filter takes out of each line."""
        return [self._token] if self._token else []

    def close(self) -> None:
        """Close each client of the site."""
        for client in self._clients:
            client.close()

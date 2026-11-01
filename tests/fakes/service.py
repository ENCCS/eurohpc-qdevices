"""The base of the fake services of the sites, for httpx.MockTransport, and a scripted answer."""

from abc import ABC, abstractmethod
from collections.abc import Callable

import httpx


def answer(code: int, **body) -> Callable[[], httpx.Response]:
    """A fresh answer of a fake service at each request."""
    return lambda: httpx.Response(code, **body)


class Service(ABC):
    """A fake service: it keeps each request, and the first route whose path end the request has answers it."""

    ROUTES: tuple[tuple[str, object], ...] = ()    # (path end, the name of the method that answers, or a fixed body)

    @abstractmethod
    def keep(self, request: httpx.Request) -> None:
        """Keep a request, in the form the tests of the service read."""

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.keep(request)
        for end, reply in self.ROUTES:
            if request.url.path.endswith(end):
                return getattr(self, reply)(request) if isinstance(reply, str) else httpx.Response(200, json=reply)
        return httpx.Response(404)

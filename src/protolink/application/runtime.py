from __future__ import annotations

import asyncio
import threading
from concurrent.futures import Future
from typing import Any


class AsyncTaskRunner:
    def __init__(self) -> None:
        self._ready = threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread = threading.Thread(target=self._run, name="ProtoLinkAsyncTaskRunner", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=5)

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        self._ready.set()
        loop.run_forever()
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.close()

    def submit(self, coroutine: Any) -> Future[Any]:
        if self._loop is None:
            raise RuntimeError("Async task runner is not ready.")
        return asyncio.run_coroutine_threadsafe(coroutine, self._loop)

    def shutdown(self) -> None:
        if self._loop is None:
            return
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=2.0)
        self._loop = None

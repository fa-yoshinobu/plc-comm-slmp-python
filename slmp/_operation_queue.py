"""Private FIFO operation-turn primitives shared by the clients."""

from __future__ import annotations

import asyncio
import threading
from collections import deque
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager

from .errors import SlmpClosedError


class _SyncFifoOperationQueue:
    """Re-entrant, generation-aware FIFO gate for synchronous operations."""

    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._waiters: deque[tuple[object, int]] = deque()
        self._owner: int | None = None
        self._owner_generation: int | None = None
        self._depth = 0
        self._generation = 0

    @contextmanager
    def turn(self) -> Iterator[None]:
        owner = threading.get_ident()
        with self._condition:
            if self._owner == owner:
                self._depth += 1
                nested = True
            else:
                nested = False
                ticket = object()
                generation = self._generation
                self._waiters.append((ticket, generation))
                while True:
                    if generation != self._generation:
                        self._waiters = deque(item for item in self._waiters if item[0] is not ticket)
                        self._condition.notify_all()
                        raise SlmpClosedError("client was closed while the operation was queued")
                    if self._owner is None and self._waiters and self._waiters[0][0] is ticket:
                        self._waiters.popleft()
                        self._owner = owner
                        self._owner_generation = generation
                        self._depth = 1
                        break
                    self._condition.wait()
        try:
            yield
        finally:
            with self._condition:
                if nested:
                    self._depth -= 1
                else:
                    self._depth -= 1
                    if self._depth == 0:
                        self._owner = None
                        self._owner_generation = None
                        self._condition.notify_all()

    def invalidate(self) -> None:
        """Reject the active and queued generation without blocking for it."""
        with self._condition:
            self._generation += 1
            self._condition.notify_all()

    def ensure_current(self) -> None:
        with self._condition:
            if (
                self._owner != threading.get_ident()
                or self._owner_generation is None
                or self._owner_generation != self._generation
            ):
                raise SlmpClosedError("client was closed during the active operation")


class _AsyncFifoOperationQueue:
    """Task-re-entrant FIFO gate with close-generation invalidation."""

    def __init__(self) -> None:
        # asyncio.Lock wakes the first waiter that started waiting.
        self.lock = asyncio.Lock()
        self._owner: asyncio.Task[object] | None = None
        self._owner_generation: int | None = None
        self._depth = 0
        self._generation = 0

    @asynccontextmanager
    async def turn(self) -> AsyncIterator[None]:
        task = asyncio.current_task()
        if task is None:
            raise RuntimeError("an asyncio task is required")
        if self._owner is task:
            self._depth += 1
            nested = True
        else:
            nested = False
            generation = self._generation
            await self.lock.acquire()
            if generation != self._generation:
                self.lock.release()
                raise SlmpClosedError("client was closed while the operation was queued")
            self._owner = task
            self._owner_generation = generation
            self._depth = 1
        try:
            yield
        finally:
            if nested:
                self._depth -= 1
            else:
                self._depth -= 1
                if self._depth == 0:
                    self._owner = None
                    self._owner_generation = None
                    self.lock.release()

    def invalidate(self) -> None:
        self._generation += 1

    def ensure_current(self) -> None:
        task = asyncio.current_task()
        if task is None or self._owner is not task or self._owner_generation != self._generation:
            raise SlmpClosedError("client was closed during the active operation")

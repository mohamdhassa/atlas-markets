"""Keep mixed synchronous DB / async broker reads off the ASGI event loop.

Only read-only handlers belong here. Execution guards remain on their original
loop. Capacity is bounded and busy requests fail promptly instead of exhausting
the shared FastAPI pool used by authentication and health checks.
"""
import asyncio
import inspect
from concurrent.futures import ThreadPoolExecutor
from functools import wraps
from threading import BoundedSemaphore

from fastapi import HTTPException

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="provider-read")
_slots = BoundedSemaphore(4)


def isolated_provider_read(handler):
    @wraps(handler)
    async def isolated(*args, **kwargs):
        if not _slots.acquire(blocking=False):
            raise HTTPException(503, "Provider views busy; retry shortly")

        def work():
            try:
                return asyncio.run(handler(*args, **kwargs))
            finally:
                _slots.release()

        future = asyncio.get_running_loop().run_in_executor(_executor, work)
        # Dependency sessions must not be closed while a worker still uses them.
        try:
            return await asyncio.shield(future)
        except asyncio.CancelledError:
            try:
                await asyncio.shield(future)
            finally:
                raise

    isolated.__signature__ = inspect.signature(handler, eval_str=True)
    return isolated

"""Bounded queues reserve a worker for short status queries."""
from concurrent.futures import Future, ThreadPoolExecutor
from threading import BoundedSemaphore


class Jobs:
    def __init__(self):
        self.pools = {"work": ThreadPoolExecutor(max_workers=2, thread_name_prefix="companion-work"),
                      "query": ThreadPoolExecutor(max_workers=1, thread_name_prefix="companion-query")}
        self.slots = {name: BoundedSemaphore(32 if name == "work" else 8) for name in self.pools}
        self.closed = False

    def submit(self, task, lane="work"):
        slot = self.slots[lane]
        if self.closed or not slot.acquire(blocking=False):
            future = Future()
            future.set_exception(RuntimeError("Too many pending operations; please retry after completion."))
            return future
        try:
            future = self.pools[lane].submit(task)
        except Exception:
            slot.release()
            raise
        future.add_done_callback(lambda _: slot.release())
        return future

    def shutdown(self, wait=False, cancel_futures=True):
        self.closed = True
        for pool in self.pools.values():
            pool.shutdown(wait=wait, cancel_futures=cancel_futures)

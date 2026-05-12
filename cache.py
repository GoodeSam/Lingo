"""Simple LRU cache for translation results."""
import threading
from collections import OrderedDict


class LRUCache:
    def __init__(self, max_size: int = 500):
        self._store: OrderedDict = OrderedDict()
        self._max = max_size
        self._lock = threading.Lock()

    def get(self, key: str) -> dict | None:
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
                return self._store[key]
            return None

    def set(self, key: str, value: dict):
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
            self._store[key] = value
            if len(self._store) > self._max:
                self._store.popitem(last=False)


_cache = LRUCache()


def lookup(text: str, mode: str) -> dict | None:
    return _cache.get(f"{mode}:{text}")


def store(text: str, mode: str, result: dict):
    _cache.set(f"{mode}:{text}", result)

"""Bounded, thread-safe TTL LRU; optional Redis caches only stateless tools."""

import copy
import hashlib
import json
import threading
import time
from collections import OrderedDict


class TTLCache:
    def __init__(self, capacity: int = 256, ttl: float = 120, clock=time.monotonic):
        if capacity < 1 or ttl <= 0:
            raise ValueError("capacity and ttl must be positive")
        self.capacity, self.ttl, self.clock = capacity, ttl, clock
        self._items = OrderedDict()
        self._lock = threading.RLock()

    def _expire(self):
        now = self.clock()
        for key in [k for k, (expires, _) in self._items.items() if expires <= now]:
            del self._items[key]

    def get(self, key):
        with self._lock:
            self._expire()
            if key not in self._items:
                return None
            self._items.move_to_end(key)
            return copy.deepcopy(self._items[key][1])

    def set(self, key, value):
        with self._lock:
            self._expire()
            self._items[key] = (self.clock() + self.ttl, copy.deepcopy(value))
            self._items.move_to_end(key)
            while len(self._items) > self.capacity:
                self._items.popitem(last=False)

    def delete(self, key) -> bool:
        with self._lock:
            self._expire()
            return self._items.pop(key, None) is not None

    def __len__(self):
        with self._lock:
            self._expire()
            return len(self._items)


class ToolCache:
    def __init__(self, ttl=120, capacity=256, redis_client=None):
        self.local = TTLCache(ttl=ttl, capacity=capacity)
        self.redis = redis_client
        self.ttl = max(1, int(ttl))
        self.redis_errors = 0

    @staticmethod
    def key(version: str, tool: str, arguments: dict) -> str:
        payload = json.dumps([version, tool, arguments], sort_keys=True, ensure_ascii=False)
        return "mtr:tool:" + hashlib.sha256(payload.encode()).hexdigest()

    def get(self, key):
        value = self.local.get(key)
        if value is not None:
            return value
        if self.redis is not None:
            try:
                raw = self.redis.get(key)
                if raw is not None:
                    value = json.loads(raw)
                    self.local.set(key, value)
                    return value
            except (ConnectionError, TimeoutError, ValueError, OSError):
                self.redis_errors += 1
            except Exception as exc:
                # Redis defines its own error tree. Do not hide programmer errors.
                if type(exc).__module__.startswith("redis"):
                    self.redis_errors += 1
                else:
                    raise
        return None

    def set(self, key, value):
        self.local.set(key, value)
        if self.redis is not None:
            try:
                self.redis.setex(key, self.ttl, json.dumps(value, ensure_ascii=False))
            except (ConnectionError, TimeoutError, ValueError, OSError):
                self.redis_errors += 1
            except Exception as exc:
                if type(exc).__module__.startswith("redis"):
                    self.redis_errors += 1
                else:
                    raise

from concurrent.futures import ThreadPoolExecutor

from mtr_agent.cache import ToolCache, TTLCache


def test_ttl_lru_and_copy_isolation():
    time = [0]
    cache = TTLCache(capacity=2, ttl=10, clock=lambda: time[0])
    cache.set("a", {"x": []})
    cache.get("a")["x"].append("changed")
    assert cache.get("a") == {"x": []}
    cache.set("b", 2)
    cache.get("a")
    cache.set("c", 3)
    assert cache.get("b") is None
    time[0] = 11
    assert cache.get("a") is None


def test_concurrency_and_versioned_cache():
    cache = TTLCache(capacity=100, ttl=30)
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda i: cache.set(str(i), i), range(100)))
    assert cache.get("99") == 99
    assert ToolCache.key("v1", "route", {"a": 1}) != ToolCache.key("v2", "route", {"a": 1})


def test_redis_failure_falls_back():
    class OfflineRedis:
        def get(self, key):
            raise ConnectionError("offline")

        def setex(self, *args):
            raise ConnectionError("offline")

    cache = ToolCache(redis_client=OfflineRedis())
    assert cache.get("missing") is None
    cache.set("a", {"answer": 1})
    assert cache.get("a") == {"answer": 1}
    assert cache.redis_errors == 2

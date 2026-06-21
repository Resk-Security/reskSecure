import time
from resksecure.cache import TrieCache


def test_cache_set_get():
    cache = TrieCache(ttl=60)
    cache.set((7, "model"), "value_7")
    assert cache.get((7, "model")) == "value_7"


def test_cache_miss():
    cache = TrieCache(ttl=60)
    assert cache.get((99, "unknown")) is None


def test_cache_ttl():
    cache = TrieCache(ttl=0.1)
    cache.set((7, "model"), "value")
    assert cache.get((7, "model")) == "value"
    time.sleep(0.15)
    assert cache.get((7, "model")) is None


def test_cache_invalidate_all():
    cache = TrieCache(ttl=60)
    cache.set((7, "a"), "v1")
    cache.set((15, "b"), "v2")
    assert len(cache) == 2
    cache.invalidate_all()
    assert len(cache) == 0


def test_cache_invalidate_by_mask():
    cache = TrieCache(ttl=60)
    cache.set((7, "a"), "v1")
    cache.set((7, "b"), "v2")
    cache.set((15, "c"), "v3")
    cache.invalidate(mask=7)
    assert cache.get((7, "a")) is None
    assert cache.get((7, "b")) is None
    assert cache.get((15, "c")) == "v3"


def test_cache_invalidate_by_model():
    cache = TrieCache(ttl=60)
    cache.set((7, "model_a"), "v1")
    cache.set((15, "model_a"), "v2")
    cache.set((7, "model_b"), "v3")
    cache.invalidate(model_name="model_a")
    assert cache.get((7, "model_a")) is None
    assert cache.get((15, "model_a")) is None
    assert cache.get((7, "model_b")) == "v3"

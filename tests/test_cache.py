import time

from schedule_cache.cache import ScheduleCache


def test_miss_then_hit(service, cache):
    _, src1, _ = service.get_group_schedule("IS-32")
    _, src2, _ = service.get_group_schedule("IS-32")
    assert (src1, src2) == ("mongo", "cache")
    st = cache.stats()
    assert st["hits"] == 1 and st["misses"] == 1


def test_key_has_ttl(service, cache):
    service.get_teacher_schedule(2)
    ttl = cache.ttl(ScheduleCache.teacher_key(2))
    assert 0 < ttl <= 60


def test_ttl_expires(repo, redis_client):
    from schedule_cache.service import ScheduleService
    cache = ScheduleCache(redis_client, ttl=1)
    svc = ScheduleService(repo, cache)
    svc.get_room_schedule("B-201")
    assert cache.exists(ScheduleCache.room_key("B-201"))
    time.sleep(1.3)
    assert not cache.exists(ScheduleCache.room_key("B-201"))
    _, src, _ = svc.get_room_schedule("B-201")
    assert src == "mongo"


def test_cached_equals_mongo(service, repo):
    rows, _, _ = service.get_group_schedule("CS-21")
    rows_cached, src, _ = service.get_group_schedule("CS-21")
    assert src == "cache"
    assert rows_cached == rows == repo.group_schedule("CS-21")

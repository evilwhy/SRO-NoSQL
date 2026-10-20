# сколько живут старые данные в кэше в разных вариантах
import os
import random
import sys
import time

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from schedule_cache import config
from schedule_cache.db import get_mongo, get_redis
from schedule_cache.repository import ScheduleRepository
from schedule_cache.cache import ScheduleCache
from schedule_cache.service import ScheduleService

LESSON = "L002"
GROUP = "IS-31"


def room_in_cache(svc):
    rows, src, _ = svc.get_group_schedule(GROUP)
    return [x for x in rows if x["lesson_id"] == LESSON][0]["room"], src


def measure_stale(svc, new_room, limit=15.0):
    t0 = time.perf_counter()
    svc.change_lesson(LESSON, {"room": new_room})
    stale = 0.0
    while time.perf_counter() - t0 < limit:
        room, src = room_in_cache(svc)
        if room == new_room:
            return round(stale, 2), src
        stale = time.perf_counter() - t0
        time.sleep(0.25)
    return round(stale, 2), "timeout"


def main():
    r = get_redis()
    repo = ScheduleRepository(get_mongo())
    orig = repo.get_lesson(LESSON)["room"]
    other = "A-205" if orig != "A-205" else "B-305"

    print("Занятие %s группы %s, аудитория сейчас %s\n" % (LESSON, GROUP, orig))

    # 1 только ttl
    cache = ScheduleCache(r, ttl=5)
    cache.clear()
    svc = ScheduleService(repo, cache, invalidate=False)
    room_in_cache(svc)
    stale, src = measure_stale(svc, other)
    print("1) только TTL=5 с, без удаления ключа:")
    print("   кэш отдавал старую аудиторию %.2f с, свежие данные пришли из %s" % (stale, src))
    svc.change_lesson(LESSON, {"room": orig})

    # 2 ttl + del
    cache = ScheduleCache(r, ttl=config.CACHE_TTL)
    cache.clear()
    svc = ScheduleService(repo, cache, invalidate=True)
    room_in_cache(svc)
    stale, src = measure_stale(svc, other)
    print("2) TTL=%d с + DEL ключей после изменения:" % config.CACHE_TTL)
    print("   кэш отдавал старую аудиторию %.2f с, свежие данные пришли из %s" % (stale, src))
    svc.change_lesson(LESSON, {"room": orig})

    # 3 гонка, делаю руками по шагам
    cache = ScheduleCache(r, ttl=5)
    cache.clear()
    svc = ScheduleService(repo, cache, invalidate=True)
    key = cache.group_key(GROUP)
    old_rows = repo.group_schedule(GROUP)          # читатель прочитал из mongo
    svc.change_lesson(LESSON, {"room": other})     # писатель обновил и удалил ключ
    cache.set(key, old_rows)                       # читатель положил старое
    t0 = time.perf_counter()
    stale = 0.0
    while True:
        room, src = room_in_cache(svc)
        if room == other:
            break
        stale = time.perf_counter() - t0
        time.sleep(0.25)
    print("3) гонка чтения и записи (читатель положил старое после DEL):")
    print("   кэш отдавал старую аудиторию %.2f с, спас только TTL=5 с" % stale)
    svc.change_lesson(LESSON, {"room": orig})

    # 4 hit ratio и время
    cache = ScheduleCache(r, ttl=config.CACHE_TTL)
    cache.clear()
    cache.reset_stats()
    svc = ScheduleService(repo, cache)
    groups = [g["code"] for g in repo.groups.find({}, {"code": 1})]
    mongo_ms, cache_ms = [], []
    for _ in range(300):
        _, src, ms = svc.get_group_schedule(random.choice(groups))
        (mongo_ms if src == "mongo" else cache_ms).append(ms)
    st = cache.stats()
    print("4) 300 случайных чтений по %d группам, TTL=%d:" % (len(groups), config.CACHE_TTL))
    print("   hits=%d misses=%d hit_ratio=%.3f" % (st["hits"], st["misses"], st["hit_ratio"]))
    print("   среднее время: mongo %.2f ms, redis %.2f ms" % (
        sum(mongo_ms) / len(mongo_ms), sum(cache_ms) / len(cache_ms)))


if __name__ == "__main__":
    main()

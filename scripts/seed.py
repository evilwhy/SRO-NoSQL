# заливка данных
import json
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from schedule_cache import config
from schedule_cache.db import get_mongo, get_redis
from schedule_cache.repository import ScheduleRepository
from schedule_cache.cache import ScheduleCache

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")


def load(name):
    with open(os.path.join(DATA, name + ".json"), encoding="utf-8") as f:
        return json.load(f)


def seed(db, r):
    for name in ("groups", "teachers", "rooms", "lessons"):
        db[name].drop()
        db[name].insert_many(load(name))
    repo = ScheduleRepository(db)
    repo.ensure_indexes()
    cache = ScheduleCache(r, config.CACHE_TTL)
    cache.clear()
    cache.reset_stats()
    return repo.counts()


if __name__ == "__main__":
    counts = seed(get_mongo(), get_redis())
    for k, v in counts.items():
        print("%-9s %d" % (k, v))
    print("кэш очищен")

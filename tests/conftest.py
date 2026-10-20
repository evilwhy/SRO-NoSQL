import os
import sys
import json

# отдельная база для тестов
os.environ["MONGO_DB"] = "university_test"
os.environ["REDIS_DB"] = "1"

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import pytest
from schedule_cache.db import get_mongo, get_redis
from schedule_cache.repository import ScheduleRepository
from schedule_cache.cache import ScheduleCache
from schedule_cache.service import ScheduleService

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")


@pytest.fixture
def repo():
    db = get_mongo()
    for name in ("groups", "teachers", "rooms", "lessons"):
        db[name].drop()
        with open(os.path.join(DATA, name + ".json"), encoding="utf-8") as f:
            db[name].insert_many(json.load(f))
    r = ScheduleRepository(db)
    r.ensure_indexes()
    return r


@pytest.fixture
def redis_client():
    r = get_redis()
    r.flushdb()
    yield r
    r.flushdb()


@pytest.fixture
def cache(redis_client):
    return ScheduleCache(redis_client, ttl=60)


@pytest.fixture
def service(repo, cache):
    return ScheduleService(repo, cache)

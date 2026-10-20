from schedule_cache.cache import ScheduleCache
from schedule_cache.service import ScheduleService


def test_change_drops_old_and_new_keys(service, cache, repo):
    l = repo.get_lesson("L001")
    service.get_group_schedule(l["group_code"])
    service.get_teacher_schedule(l["teacher_id"])
    service.get_room_schedule(l["room"])
    service.get_room_schedule("B-201")
    assert cache.stats()["cached_keys"] == 4

    keys = service.change_lesson("L001", {"room": "B-201"})
    assert set(keys) == {
        ScheduleCache.group_key(l["group_code"]),
        ScheduleCache.teacher_key(l["teacher_id"]),
        ScheduleCache.room_key(l["room"]),
        ScheduleCache.room_key("B-201"),
    }
    assert cache.stats()["cached_keys"] == 0


def test_read_after_change_is_fresh(service, repo):
    service.get_group_schedule("IS-31")
    service.change_lesson("L002", {"room": "A-205"})
    rows, src, _ = service.get_group_schedule("IS-31")
    assert src == "mongo"
    assert [r for r in rows if r["lesson_id"] == "L002"][0]["room"] == "A-205"


def test_stale_without_invalidation(repo, cache):
    svc = ScheduleService(repo, cache, invalidate=False)
    svc.get_group_schedule("IS-31")
    svc.change_lesson("L002", {"room": "A-205"})
    rows, src, _ = svc.get_group_schedule("IS-31")
    assert src == "cache"
    # старая аудитория, stale
    assert [r for r in rows if r["lesson_id"] == "L002"][0]["room"] != "A-205"


def test_add_and_remove_invalidate(service, cache):
    service.get_group_schedule("IT-41")
    lesson = {"lesson_id": "L900", "group_code": "IT-41", "subject": "Консультация", "teacher_id": 2,
              "room": "A-205", "weekday": 6, "start": "09:30", "end": "10:50", "kind": "практика"}
    service.add_lesson(lesson)
    assert not cache.exists(ScheduleCache.group_key("IT-41"))
    rows, _, _ = service.get_group_schedule("IT-41")
    assert any(r["lesson_id"] == "L900" for r in rows)

    service.remove_lesson("L900")
    rows, src, _ = service.get_group_schedule("IT-41")
    assert src == "mongo"
    assert not any(r["lesson_id"] == "L900" for r in rows)


def test_change_unknown_lesson_raises(service):
    import pytest
    with pytest.raises(KeyError):
        service.change_lesson("L000", {"room": "A-205"})

def test_seed_counts(repo):
    c = repo.counts()
    assert c["lessons"] >= 30
    assert c["groups"] == 6


def test_crud_lesson(repo):
    lesson = {"lesson_id": "L999", "group_code": "IS-31", "subject": "Тест", "teacher_id": 1,
              "room": "A-205", "weekday": 6, "start": "13:00", "end": "14:20", "kind": "практика"}
    repo.add_lesson(lesson)
    assert repo.get_lesson("L999")["subject"] == "Тест"

    old = repo.update_lesson("L999", {"room": "B-305"})
    assert old["room"] == "A-205"
    assert repo.get_lesson("L999")["room"] == "B-305"

    repo.delete_lesson("L999")
    assert repo.get_lesson("L999") is None


def test_group_schedule_sorted_and_joined(repo):
    rows = repo.group_schedule("IS-31")
    assert len(rows) == 8
    assert all("teacher" in r and "building" in r for r in rows)
    order = [(r["weekday"], r["start"]) for r in rows]
    assert order == sorted(order)


def test_free_rooms_excludes_busy(repo):
    l = repo.get_lesson("L001")
    free = [r["room"] for r in repo.free_rooms(l["weekday"], l["start"])]
    assert l["room"] not in free


def test_conflicts_found(repo):
    c = repo.room_conflicts()
    assert len(c) == 1
    assert c[0]["room"] == "B-202"

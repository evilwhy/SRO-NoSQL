# запускать после seed.py
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from schedule_cache import config
from schedule_cache.db import get_mongo, get_redis
from schedule_cache.repository import ScheduleRepository
from schedule_cache.cache import ScheduleCache
from schedule_cache.service import ScheduleService

WD = config.WEEKDAYS


def title(n, text):
    print("\n=== Q%d. %s ===" % (n, text))


def show(rows, src, ms):
    print("источник: %s, %.2f ms, %d занятий" % (src, ms, len(rows)))
    for l in rows:
        print("  %s %s-%s  %-28s %-9s %-6s %-15s %s" % (
            WD[l["weekday"]], l["start"], l["end"], l["subject"], l["kind"], l["room"], l["teacher"], l.get("group_code", "")))


def main():
    r = get_redis()
    repo = ScheduleRepository(get_mongo())
    cache = ScheduleCache(r, config.CACHE_TTL)
    svc = ScheduleService(repo, cache)
    cache.clear()
    cache.reset_stats()

    title(1, "Расписание группы IS-31 на неделю, два раза подряд (miss, потом hit)")
    rows, src, ms = svc.get_group_schedule("IS-31")
    show(rows, src, ms)
    rows, src, ms = svc.get_group_schedule("IS-31")
    print("второй раз: источник %s, %.2f ms, ttl ключа %s с" % (src, ms, cache.ttl(cache.group_key("IS-31"))))

    title(2, "Расписание группы IS-31 на вторник (фильтр по недельному кэшу)")
    rows, src, ms = svc.get_group_day("IS-31", 2)
    show(rows, src, ms)

    title(3, "Расписание преподавателя 2 (Нурланова Д.К.)")
    rows, src, ms = svc.get_teacher_schedule(2)
    show(rows, src, ms)

    title(4, "Занятость аудитории B-201")
    rows, src, ms = svc.get_room_schedule("B-201")
    show(rows, src, ms)

    title(5, "Свободные аудитории в четверг в 14:30 ($lookup с pipeline)")
    for room in repo.free_rooms(4, "14:30"):
        print("  %-6s корпус %s, %3d мест, %s" % (room["room"], room["building"], room["capacity"], room["type"]))

    title(6, "Нагрузка преподавателей ($group + $lookup)")
    for t in repo.teacher_load():
        print("  %-16s %2d пар  %4.1f ч/нед  %d групп" % (t["name"], t["lessons"], t["hours"], t["groups"]))

    title(7, "Конфликты аудиторий: две группы в одной аудитории в одно время")
    for c in repo.room_conflicts():
        print("  %s %s %s: группы %s, занятия %s" % (c["room"], WD[c["weekday"]], c["start"], c["groups"], c["lessons"]))

    title(8, "Перенос пары L001 в другую аудиторию: инвалидация и чтение после")
    old = repo.get_lesson("L001")
    print("  было: %s %s %s %s" % (old["group_code"], WD[old["weekday"]], old["start"], old["room"]))
    print("  ключи в кэше до:", sorted(r.keys("schedule:*")))
    keys = svc.change_lesson("L001", {"room": "B-201"})
    print("  сброшены:", keys)
    print("  ключи в кэше после:", sorted(r.keys("schedule:*")))
    rows, src, ms = svc.get_group_schedule("IS-31")
    l = [x for x in rows if x["lesson_id"] == "L001"][0]
    print("  стало: %s %s %s %s  [источник %s]" % (l["group_code"], WD[l["weekday"]], l["start"], l["room"], src))
    # откат
    svc.change_lesson("L001", {"room": old["room"]})

    title(9, "Поиск по предмету (regex)")
    for l in repo.lessons_by_subject("nosql"):
        print("  %s %-6s %s %s %s" % (l["lesson_id"], l["group_code"], WD[l["weekday"]], l["start"], l["kind"]))

    title(10, "Статистика кэша")
    for k, v in cache.stats().items():
        print("  %-14s %s" % (k, v))


if __name__ == "__main__":
    main()

"""CLI для демо.

  python scripts/schedule.py group IS-31
  python scripts/schedule.py group IS-31 --day 2
  python scripts/schedule.py teacher 2
  python scripts/schedule.py room B-201
  python scripts/schedule.py move L005 --room B-202 --weekday 3 --start 11:00 --end 12:20
  python scripts/schedule.py add --group IS-31 --subject "Консультация" --teacher 2 --room A-205 --weekday 6 --start 09:30 --end 10:50
  python scripts/schedule.py remove L999
  python scripts/schedule.py stats
  python scripts/schedule.py keys
"""
import argparse
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from schedule_cache import config
from schedule_cache.db import get_mongo, get_redis
from schedule_cache.repository import ScheduleRepository
from schedule_cache.cache import ScheduleCache
from schedule_cache.service import ScheduleService


def print_schedule(rows, source, ms, title):
    print("%s  [%s, %.2f ms]" % (title, source, ms))
    if not rows:
        print("  пусто")
    for l in rows:
        print("  %s %s-%s  %-28s %-9s %-6s %-15s %s" % (
            config.WEEKDAYS[l["weekday"]], l["start"], l["end"], l["subject"], l["kind"],
            l["room"], l["teacher"], l.get("group_code", "")))


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("group"); g.add_argument("code"); g.add_argument("--day", type=int)
    t = sub.add_parser("teacher"); t.add_argument("id", type=int)
    rm = sub.add_parser("room"); rm.add_argument("room")
    m = sub.add_parser("move"); m.add_argument("lesson_id")
    for name in ("room", "start", "end"):
        m.add_argument("--" + name)
    m.add_argument("--weekday", type=int)
    a = sub.add_parser("add")
    for name in ("group", "subject", "room", "start", "end"):
        a.add_argument("--" + name, required=True)
    a.add_argument("--teacher", type=int, required=True)
    a.add_argument("--weekday", type=int, required=True)
    a.add_argument("--kind", default="практика")
    d = sub.add_parser("remove"); d.add_argument("lesson_id")
    sub.add_parser("stats")
    sub.add_parser("keys")
    args = p.parse_args()

    r = get_redis()
    r.ping()  # иначе первый запрос считает еще и коннект
    repo = ScheduleRepository(get_mongo())
    cache = ScheduleCache(r, config.CACHE_TTL)
    svc = ScheduleService(repo, cache)

    if args.cmd == "group":
        if args.day:
            rows, src, ms = svc.get_group_day(args.code, args.day)
            print_schedule(rows, src, ms, "Группа %s, %s" % (args.code, config.WEEKDAYS[args.day]))
        else:
            rows, src, ms = svc.get_group_schedule(args.code)
            print_schedule(rows, src, ms, "Группа %s, неделя" % args.code)
    elif args.cmd == "teacher":
        rows, src, ms = svc.get_teacher_schedule(args.id)
        print_schedule(rows, src, ms, "Преподаватель %d" % args.id)
    elif args.cmd == "room":
        rows, src, ms = svc.get_room_schedule(args.room)
        print_schedule(rows, src, ms, "Аудитория %s" % args.room)
    elif args.cmd == "move":
        changes = {k: v for k, v in vars(args).items() if k in ("room", "weekday", "start", "end") and v is not None}
        keys = svc.change_lesson(args.lesson_id, changes)
        print("изменено:", changes)
        print("сброшены ключи:", keys)
    elif args.cmd == "add":
        last = repo.lessons.find_one(sort=[("lesson_id", -1)])
        lesson_id = "L%03d" % (int(last["lesson_id"][1:]) + 1) if last else "L001"
        lesson = {"lesson_id": lesson_id, "group_code": args.group, "subject": args.subject,
                  "teacher_id": args.teacher, "room": args.room, "weekday": args.weekday,
                  "start": args.start, "end": args.end, "kind": args.kind}
        keys = svc.add_lesson(lesson)
        print("добавлено:", lesson_id)
        print("сброшены ключи:", keys)
    elif args.cmd == "remove":
        keys = svc.remove_lesson(args.lesson_id)
        print("удалено:", args.lesson_id)
        print("сброшены ключи:", keys)
    elif args.cmd == "stats":
        for k, v in cache.stats().items():
            print("%-14s %s" % (k, v))
    elif args.cmd == "keys":
        for k in sorted(r.keys("schedule:*")):
            print("%-28s ttl=%ss" % (k, r.ttl(k)))


if __name__ == "__main__":
    main()

# тут вся логика кэша
import time

from .cache import ScheduleCache


class ScheduleService:
    def __init__(self, repo, cache, invalidate=True):
        self.repo = repo
        self.cache = cache
        # invalidate=False только для stale_analysis.py
        self.invalidate = invalidate

    def _cached(self, key, loader):
        t0 = time.perf_counter()
        data = self.cache.get(key)
        source = "cache"
        if data is None:
            data = loader()
            self.cache.set(key, data)
            source = "mongo"
        ms = (time.perf_counter() - t0) * 1000
        return data, source, round(ms, 2)

    def get_group_schedule(self, code):
        return self._cached(ScheduleCache.group_key(code), lambda: self.repo.group_schedule(code))

    def get_teacher_schedule(self, teacher_id):
        return self._cached(ScheduleCache.teacher_key(teacher_id), lambda: self.repo.teacher_schedule(teacher_id))

    def get_room_schedule(self, room):
        return self._cached(ScheduleCache.room_key(room), lambda: self.repo.room_schedule(room))

    def get_group_day(self, code, weekday):
        # отдельный ключ на день не делаю, беру из недели
        week, source, ms = self.get_group_schedule(code)
        return [l for l in week if l["weekday"] == weekday], source, ms

    @staticmethod
    def keys_for(lesson):
        if lesson is None:
            return []
        return [
            ScheduleCache.group_key(lesson["group_code"]),
            ScheduleCache.teacher_key(lesson["teacher_id"]),
            ScheduleCache.room_key(lesson["room"]),
        ]

    def _drop(self, *lessons):
        if not self.invalidate:
            return []
        keys = []
        for l in lessons:
            for k in self.keys_for(l):
                if k not in keys:
                    keys.append(k)
        self.cache.delete(*keys)
        return keys

    def add_lesson(self, lesson):
        self.repo.add_lesson(lesson)
        return self._drop(lesson)

    def change_lesson(self, lesson_id, changes):
        old = self.repo.update_lesson(lesson_id, changes)
        if old is None:
            raise KeyError("нет занятия %s" % lesson_id)
        new = self.repo.get_lesson(lesson_id)
        # old и new оба нужны, иначе при переносе в другую аудиторию у нее останется старый кэш
        return self._drop(old, new)

    def remove_lesson(self, lesson_id):
        old = self.repo.delete_lesson(lesson_id)
        if old is None:
            raise KeyError("нет занятия %s" % lesson_id)
        return self._drop(old)

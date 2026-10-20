# все что ходит в mongo
from pymongo import ASCENDING


class ScheduleRepository:
    def __init__(self, db):
        self.db = db
        self.lessons = db.lessons
        self.groups = db.groups
        self.teachers = db.teachers
        self.rooms = db.rooms

    def ensure_indexes(self):
        self.lessons.create_index("lesson_id", unique=True)
        self.lessons.create_index([("group_code", ASCENDING), ("weekday", ASCENDING), ("start", ASCENDING)])
        self.lessons.create_index([("teacher_id", ASCENDING), ("weekday", ASCENDING)])
        self.lessons.create_index([("room", ASCENDING), ("weekday", ASCENDING), ("start", ASCENDING)])
        self.groups.create_index("code", unique=True)
        self.teachers.create_index("teacher_id", unique=True)
        self.rooms.create_index("room", unique=True)

    def add_lesson(self, lesson):
        self.lessons.insert_one(dict(lesson))
        return lesson["lesson_id"]

    def get_lesson(self, lesson_id):
        return self.lessons.find_one({"lesson_id": lesson_id}, {"_id": 0})

    def update_lesson(self, lesson_id, changes):
        # find_one_and_update возвращает старый документ, он нужен для сброса кэша
        old = self.lessons.find_one_and_update(
            {"lesson_id": lesson_id}, {"$set": changes}, projection={"_id": 0})
        return old

    def delete_lesson(self, lesson_id):
        return self.lessons.find_one_and_delete({"lesson_id": lesson_id}, projection={"_id": 0})

    # это кладется в кэш
    def _schedule(self, match):
        pipeline = [
            {"$match": match},
            {"$lookup": {"from": "teachers", "localField": "teacher_id",
                         "foreignField": "teacher_id", "as": "t"}},
            {"$unwind": "$t"},
            {"$lookup": {"from": "rooms", "localField": "room",
                         "foreignField": "room", "as": "r"}},
            {"$unwind": "$r"},
            {"$project": {"_id": 0, "lesson_id": 1, "group_code": 1, "weekday": 1,
                          "start": 1, "end": 1, "subject": 1, "kind": 1, "room": 1,
                          "building": "$r.building", "teacher": "$t.name"}},
            {"$sort": {"weekday": 1, "start": 1}},
        ]
        return list(self.lessons.aggregate(pipeline))

    def group_schedule(self, group_code):
        return self._schedule({"group_code": group_code})

    def teacher_schedule(self, teacher_id):
        return self._schedule({"teacher_id": teacher_id})

    def room_schedule(self, room):
        return self._schedule({"room": room})

    def free_rooms(self, weekday, start):
        # lookup с pipeline, busy пустой = свободна
        pipeline = [
            {"$lookup": {
                "from": "lessons",
                "let": {"r": "$room"},
                "pipeline": [{"$match": {"$expr": {"$and": [
                    {"$eq": ["$room", "$$r"]},
                    {"$eq": ["$weekday", weekday]},
                    {"$eq": ["$start", start]},
                ]}}}],
                "as": "busy"}},
            {"$match": {"busy": {"$size": 0}}},
            {"$project": {"_id": 0, "room": 1, "building": 1, "capacity": 1, "type": 1}},
            {"$sort": {"room": 1}},
        ]
        return list(self.rooms.aggregate(pipeline))

    def teacher_load(self):
        # пара 80 мин
        pipeline = [
            {"$group": {"_id": "$teacher_id", "lessons": {"$sum": 1},
                        "groups": {"$addToSet": "$group_code"}}},
            {"$lookup": {"from": "teachers", "localField": "_id",
                         "foreignField": "teacher_id", "as": "t"}},
            {"$unwind": "$t"},
            {"$project": {"_id": 0, "teacher_id": "$_id", "name": "$t.name",
                          "lessons": 1, "groups": {"$size": "$groups"},
                          "hours": {"$round": [{"$divide": [{"$multiply": ["$lessons", 80]}, 60]}, 1]}}},
            {"$sort": {"lessons": -1, "name": 1}},
        ]
        return list(self.lessons.aggregate(pipeline))

    def room_conflicts(self):
        pipeline = [
            {"$group": {"_id": {"room": "$room", "weekday": "$weekday", "start": "$start"},
                        "count": {"$sum": 1},
                        "groups": {"$push": "$group_code"},
                        "lessons": {"$push": "$lesson_id"}}},
            {"$match": {"count": {"$gt": 1}}},
            {"$project": {"_id": 0, "room": "$_id.room", "weekday": "$_id.weekday",
                          "start": "$_id.start", "groups": 1, "lessons": 1}},
        ]
        return list(self.lessons.aggregate(pipeline))

    def lessons_by_subject(self, text):
        return list(self.lessons.find(
            {"subject": {"$regex": text, "$options": "i"}},
            {"_id": 0, "lesson_id": 1, "group_code": 1, "subject": 1, "weekday": 1, "start": 1, "kind": 1}
        ).sort([("group_code", 1), ("weekday", 1)]))

    def counts(self):
        return {name: self.db[name].count_documents({}) for name in ("groups", "teachers", "rooms", "lessons")}

# обертка над redis
import json


class ScheduleCache:
    def __init__(self, r, ttl):
        self.r = r
        self.default_ttl = ttl

    @staticmethod
    def group_key(code):
        return "schedule:group:%s" % code

    @staticmethod
    def teacher_key(teacher_id):
        return "schedule:teacher:%s" % teacher_id

    @staticmethod
    def room_key(room):
        return "schedule:room:%s" % room

    def get(self, key):
        raw = self.r.get(key)
        if raw is None:
            self.r.incr("stats:misses")
            return None
        self.r.incr("stats:hits")
        return json.loads(raw)

    def set(self, key, value, ttl=None):
        self.r.set(key, json.dumps(value, ensure_ascii=False), ex=ttl or self.default_ttl)

    def delete(self, *keys):
        if not keys:
            return 0
        n = self.r.delete(*keys)
        self.r.incrby("stats:invalidations", len(keys))
        return n

    def ttl(self, key):
        return self.r.ttl(key)

    def exists(self, key):
        return self.r.exists(key) == 1

    def stats(self):
        hits = int(self.r.get("stats:hits") or 0)
        misses = int(self.r.get("stats:misses") or 0)
        total = hits + misses
        return {
            "hits": hits,
            "misses": misses,
            "invalidations": int(self.r.get("stats:invalidations") or 0),
            "hit_ratio": round(hits / total, 3) if total else 0.0,
            "cached_keys": len(self.r.keys("schedule:*")),
        }

    def reset_stats(self):
        self.r.delete("stats:hits", "stats:misses", "stats:invalidations")

    def clear(self):
        keys = self.r.keys("schedule:*")
        if keys:
            self.r.delete(*keys)
        return len(keys)

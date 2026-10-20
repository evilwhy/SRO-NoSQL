from pymongo import MongoClient
import redis

from . import config


def get_mongo():
    client = MongoClient(config.MONGO_URI, serverSelectionTimeoutMS=3000)
    return client[config.MONGO_DB]


def get_redis():
    return redis.Redis(host=config.REDIS_HOST, port=config.REDIS_PORT,
                       db=config.REDIS_DB, decode_responses=True)

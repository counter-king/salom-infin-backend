import redis
import os

# Singleton Redis client (thread-safe)
redis_client = redis.StrictRedis(
    host=os.getenv('BROKER_IP'),
    port=6379,
    db=0,
    decode_responses=True
)

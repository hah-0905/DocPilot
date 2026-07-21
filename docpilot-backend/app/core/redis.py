from redis.asyncio import Redis

redis_client = Redis(
    host="localhost",
    port=6379,
    db=0,
    password="123456",
    decode_responses=True
)
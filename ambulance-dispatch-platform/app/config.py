import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://ambulance:ambulance@localhost:5432/ambulance_db",
)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/%2F")
LOCATION_TTL_SECONDS = int(os.getenv("LOCATION_TTL_SECONDS", "30"))

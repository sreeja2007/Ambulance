import json
import logging
import pika
from app.config import RABBITMQ_URL

log = logging.getLogger(__name__)
QUEUE = "emergency_events"

def publish_event(event: dict):
    """Best-effort publisher for the demo. Production: use a transactional outbox."""
    connection = None
    try:
        params = pika.URLParameters(RABBITMQ_URL)
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        channel.queue_declare(queue=QUEUE, durable=True)
        channel.basic_publish(
            exchange="", routing_key=QUEUE,
            body=json.dumps(event).encode(),
            properties=pika.BasicProperties(delivery_mode=2, content_type="application/json"),
        )
    except Exception:
        log.exception("Could not publish event; production should persist/retry via outbox")
    finally:
        if connection and connection.is_open:
            connection.close()

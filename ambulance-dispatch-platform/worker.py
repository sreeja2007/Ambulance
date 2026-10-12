import json
import logging
import pika
from app.config import RABBITMQ_URL

logging.basicConfig(level=logging.INFO)
QUEUE = "emergency_events"

def main():
    params = pika.URLParameters(RABBITMQ_URL)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    channel.queue_declare(queue=QUEUE, durable=True)
    channel.basic_qos(prefetch_count=10)

    def handle(ch, method, properties, body):
        try:
            event = json.loads(body)
            logging.info("Received event: %s", event)
            # TODO: send push notification / call external alert provider.
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception:
            logging.exception("Event processing failed")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    channel.basic_consume(queue=QUEUE, on_message_callback=handle)
    logging.info("Waiting for events...")
    channel.start_consuming()

if __name__ == "__main__":
    main()

import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from banking_common.config import get_settings
from banking_common.events import build_event, parse_event
from banking_common.metrics import event_failures_total

logger = logging.getLogger(__name__)


class KafkaPublisher:
    def __init__(self) -> None:
        self._producer: AIOKafkaProducer | None = None

    async def start(self) -> None:
        self._producer = AIOKafkaProducer(
            bootstrap_servers=get_settings().kafka_bootstrap_servers,
            value_serializer=lambda value: json.dumps(value, default=str).encode("utf-8"),
        )
        await self._producer.start()

    async def stop(self) -> None:
        if self._producer:
            await self._producer.stop()

    async def publish(self, topic: str, payload: dict[str, Any]) -> None:
        if self._producer is None:
            raise RuntimeError("Kafka producer is not started")
        await self._producer.send_and_wait(topic, payload)

    async def publish_event(
        self,
        topic: str,
        event_type: str,
        payload: dict[str, Any],
        correlation_id: str | None = None,
    ) -> None:
        await self.publish(topic, build_event(event_type, payload, correlation_id))


async def consume_forever(
    topics: list[str],
    group_id: str,
    handler: Callable[[str, dict[str, Any]], Awaitable[None]],
    *,
    max_retries: int = 3,
    dlq_suffix: str = ".dlq",
) -> None:
    consumer = AIOKafkaConsumer(
        *topics,
        bootstrap_servers=get_settings().kafka_bootstrap_servers,
        group_id=group_id,
        value_deserializer=lambda raw: json.loads(raw.decode("utf-8")),
        enable_auto_commit=True,
        auto_offset_reset="earliest",
    )
    dlq_producer = AIOKafkaProducer(
        bootstrap_servers=get_settings().kafka_bootstrap_servers,
        value_serializer=lambda value: json.dumps(value, default=str).encode("utf-8"),
    )
    await consumer.start()
    try:
        await dlq_producer.start()
    except Exception:
        await consumer.stop()
        raise
    try:
        async for message in consumer:
            event_type = "unknown"
            try:
                envelope, _payload = parse_event(message.value)
                event_type = envelope.event_type
                for attempt in range(1, max_retries + 1):
                    try:
                        await handler(message.topic, message.value)
                        break
                    except Exception:
                        if attempt == max_retries:
                            raise
                        logger.exception("Kafka handler retry topic=%s attempt=%s", message.topic, attempt)
            except Exception as exc:
                event_failures_total.labels(topic=message.topic, event_type=event_type).inc()
                logger.exception("Kafka handler failed topic=%s event_type=%s", message.topic, event_type)
                await dlq_producer.send_and_wait(
                    f"{message.topic}{dlq_suffix}",
                    {
                        "source_topic": message.topic,
                        "error": str(exc),
                        "raw_message": message.value,
                    },
                )
    finally:
        await consumer.stop()
        await dlq_producer.stop()

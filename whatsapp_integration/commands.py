from celery import shared_task
import logging
from .models import WhatsAppWebhookEvent, WhatsAppMessage
from django.db import transaction

logger = logging.getLogger(__name__)
HANDLERS = {}

def register_handler(name):
    def _wrap(fn):
        HANDLERS[name] = fn
        return fn
    return _wrap

@shared_task(bind=True)
def dispatch_event(self, event_id):
    try:
        event = WhatsAppWebhookEvent.objects.get(pk=event_id)
    except WhatsAppWebhookEvent.DoesNotExist:
        return

    if event.processed:
        return

    payload = event.payload
    # very basic parsing: create echo messages for text received
    try:
        entries = payload.get("entry", [])
        with transaction.atomic():
            for e in entries:
                changes = e.get("changes", [])
                for ch in changes:
                    val = ch.get("value", {})
                    messages = val.get("messages", [])
                    for m in messages:
                        from_phone = m.get("from")
                        text = (m.get("text") or {}).get("body")
                        if text:
                            WhatsAppMessage.objects.create(
                                recipient=from_phone,
                                message_type="text",
                                payload={"body": f"Echo: {text}"}
                            )
            event.processed = True
            event.save(update_fields=["processed"])
    except Exception:
        raise


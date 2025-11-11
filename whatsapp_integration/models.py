from django.db import models
from django.utils import timezone
import uuid

class WhatsAppMessage(models.Model):
    MESSAGE_TYPES = (("text", "text"), ("template", "template"))
    STATUS_CHOICES = (
        ("queued", "queued"),
        ("processing", "processing"),
        ("sent", "sent"),
        ("delivered", "delivered"),
        ("failed", "failed"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.CharField(max_length=64, db_index=True)
    message_type = models.CharField(max_length=16, choices=MESSAGE_TYPES)
    payload = models.JSONField()
    status = models.CharField(max_length=32, default="queued", db_index=True, choices=STATUS_CHOICES)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.TextField(null=True, blank=True)
    external_id = models.CharField(max_length=128, null=True, blank=True, db_index=True)
    idempotency_key = models.CharField(max_length=128, null=True, blank=True, unique=True)
    template_name = models.CharField(max_length=128, null=True, blank=True)
    template_language = models.CharField(max_length=16, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["recipient", "status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.message_type} -> {self.recipient} ({self.status})"


class WhatsAppWebhookEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_id = models.CharField(max_length=256, unique=True, db_index=True)
    payload = models.JSONField()
    processed = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"event {self.event_id} processed={self.processed}"

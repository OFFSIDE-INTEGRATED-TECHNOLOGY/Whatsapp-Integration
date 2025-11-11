from rest_framework import serializers
from .models import WhatsAppWebhookEvent

class WhatsAppWebhookEventSerializer(serializers.ModelSerializer):
    """Serializer to validate and store webhook payloads."""
    payload = serializers.JSONField()

    class Meta:
        model = WhatsAppWebhookEvent
        fields = ["id", "event_id", "payload", "processed"]
        read_only_fields = ["id", "event_id", "processed"]

from django.contrib import admin
from .models import WhatsAppMessage, WhatsAppWebhookEvent

@admin.register(WhatsAppMessage)
class WhatsAppMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "recipient", "message_type", "status", "attempts", "created_at")
    list_filter = ("status", "message_type")
    search_fields = ("recipient", "external_id", "idempotency_key")

@admin.register(WhatsAppWebhookEvent)
class WhatsAppWebhookEventAdmin(admin.ModelAdmin):
    list_display = ("event_id", "processed", "created_at")
    search_fields = ("event_id",)

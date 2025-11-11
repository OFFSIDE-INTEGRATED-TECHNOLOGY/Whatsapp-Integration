from django.urls import path
from .views import WhatsAppWebhookReceiveView, WhatsAppWebhookVerifyView

urlpatterns = [
    path("webhook/", WhatsAppWebhookReceiveView.as_view(), name="whatsapp_webhook"),
    path("webhook/verify/", WhatsAppWebhookVerifyView.as_view(), name="whatsapp_verify"),
]

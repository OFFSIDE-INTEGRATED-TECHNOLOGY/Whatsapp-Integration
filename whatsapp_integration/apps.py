from django.apps import AppConfig

class WhatsAppIntegrationConfig(AppConfig):
    name = "whatsapp_integration"
    verbose_name = "WhatsApp Integration"

    def ready(self):
        # place to import signal handlers or register pluggable handlers
        pass

from django.apps import AppConfig

class WhatsAppIntegrationConfig(AppConfig):
    name = "whatsapp_integration"
    verbose_name = "WhatsApp Integration"

    def ready(self):
        
        pass

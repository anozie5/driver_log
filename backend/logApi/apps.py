from django.apps import AppConfig


class LogapiConfig(AppConfig):
    name = 'logApi'

    def ready(self):
        import logApi.signals as log_signals
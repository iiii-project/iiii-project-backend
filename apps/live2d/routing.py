from django.urls import path

from .consumers import Live2DConsumer

websocket_urlpatterns = [
    path("client-ws", Live2DConsumer.as_asgi()),
]

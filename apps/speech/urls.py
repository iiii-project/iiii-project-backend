from django.urls import path

from .views import TranscribeView

urlpatterns = [
    path("speech/transcribe/", TranscribeView.as_view(), name="speech-transcribe"),
]

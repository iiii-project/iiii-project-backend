from django.urls import path

from .views import FortuneSetListView

urlpatterns = [
    path("fortune-sets/", FortuneSetListView.as_view(), name="fortune-set-list"),
]

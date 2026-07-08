from django.urls import path

from .views import FortuneDetailView, FortuneSetListView

urlpatterns = [
    path("fortune-sets/", FortuneSetListView.as_view(), name="fortune-set-list"),
    path("fortune-sets/<str:fortune_set_code>/fortunes/<int:number>/", FortuneDetailView.as_view(), name="fortune-detail"),
]

from django.urls import path

from .views import HealthView, HomeContentView
from .views import UsageStatsView

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("home/", HomeContentView.as_view(), name="home-content"),
    path("admin/usage-stats/", UsageStatsView.as_view(), name="usage-stats"),
]

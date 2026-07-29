from django.urls import path

from .views import (
    BlockCastView,
    ChatView,
    ClaimView,
    DivinationDetailView,
    DivinationListCreateView,
    DrawFortuneView,
    InterpretView,
    PrayerCompleteView,
)

urlpatterns = [
    path("divinations/", DivinationListCreateView.as_view(), name="divination-list-create"),
    path("divinations/<uuid:session_id>/", DivinationDetailView.as_view(), name="divination-detail"),
    path("divinations/<uuid:session_id>/prayer-complete/", PrayerCompleteView.as_view(), name="prayer-complete"),
    path("divinations/<uuid:session_id>/draw/", DrawFortuneView.as_view(), name="draw-fortune"),
    path("divinations/<uuid:session_id>/blocks/", BlockCastView.as_view(), name="cast-blocks"),
    path("divinations/<uuid:session_id>/interpret/", InterpretView.as_view(), name="interpret"),
    path("divinations/<uuid:session_id>/chat/", ChatView.as_view(), name="chat"),
    path("divinations/<uuid:session_id>/claim/", ClaimView.as_view(), name="claim-session"),
]

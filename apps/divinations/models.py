import uuid

from django.conf import settings
from django.db import models


class DivinationSession(models.Model):
    CATEGORY_CHOICES = [
        ("love", "感情"),
        ("career", "工作"),
        ("study", "學業"),
        ("wealth", "財運"),
        ("health", "健康"),
        ("family", "家庭"),
        ("relationship", "人際"),
        ("travel", "出行"),
        ("other", "其他"),
    ]
    INTERACTION_CHOICES = [("click", "點擊"), ("motion", "動作辨識")]
    STATUS_CHOICES = [
        ("created", "Created"),
        ("praying", "Praying"),
        ("drawing", "Drawing"),
        ("waiting_for_blocks", "Waiting for blocks"),
        ("confirmed", "Confirmed"),
        ("rejected", "Rejected"),
        ("interpreting", "Interpreting"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    session_uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="divination_sessions",
    )
    anonymous_user_id = models.CharField(max_length=100, blank=True)
    fortune_set = models.ForeignKey("fortunes.FortuneSet", on_delete=models.PROTECT, related_name="sessions")
    fortune = models.ForeignKey(
        "fortunes.Fortune", null=True, blank=True, on_delete=models.PROTECT, related_name="sessions"
    )
    question = models.TextField()
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    categories = models.JSONField(default=list, blank=True)
    interaction_mode = models.CharField(max_length=20, choices=INTERACTION_CHOICES)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="created")
    confirmed = models.BooleanField(default=False)
    ai_interpretation = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return str(self.session_uuid)


class BlockCast(models.Model):
    SIDE_CHOICES = [("flat", "平面"), ("round", "凸面")]
    RESULT_CHOICES = [("sheng", "聖筊"), ("xiao", "笑筊"), ("yin", "陰筊")]

    divination_session = models.ForeignKey(DivinationSession, on_delete=models.CASCADE, related_name="block_casts")
    attempt_number = models.PositiveIntegerField()
    block_one = models.CharField(max_length=10, choices=SIDE_CHOICES)
    block_two = models.CharField(max_length=10, choices=SIDE_CHOICES)
    result = models.CharField(max_length=20, choices=RESULT_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["divination_session", "attempt_number"], name="unique_block_attempt_in_session"
            )
        ]
        ordering = ["divination_session", "attempt_number"]

    def __str__(self) -> str:
        return f"{self.divination_session_id} #{self.attempt_number} {self.result}"

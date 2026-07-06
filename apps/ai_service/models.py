from django.db import models


class AIMessage(models.Model):
    ROLE_CHOICES = [("system", "System"), ("user", "User"), ("assistant", "Assistant")]

    divination_session = models.ForeignKey(
        "divinations.DivinationSession", on_delete=models.CASCADE, related_name="ai_messages"
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    model_name = models.CharField(max_length=100, blank=True)
    token_count = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self) -> str:
        return f"{self.divination_session_id} {self.role}"

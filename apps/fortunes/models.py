from django.db import models


class FortuneSet(models.Model):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    source_name = models.CharField(max_length=200, blank=True)
    version = models.CharField(max_length=30, blank=True)
    prompt_template = models.TextField(blank=True)
    is_default = models.BooleanField(default=False)
    is_public = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class Fortune(models.Model):
    fortune_set = models.ForeignKey(FortuneSet, on_delete=models.CASCADE, related_name="fortunes")
    number = models.PositiveIntegerField()
    title = models.CharField(max_length=100, blank=True)
    ganzhi = models.CharField(max_length=20, blank=True)
    fortune_level = models.CharField(max_length=30, blank=True)
    poem = models.TextField()
    translation = models.TextField(blank=True)
    story = models.TextField(blank=True)
    general_meaning = models.TextField(blank=True)
    love_meaning = models.TextField(blank=True)
    career_meaning = models.TextField(blank=True)
    study_meaning = models.TextField(blank=True)
    wealth_meaning = models.TextField(blank=True)
    health_meaning = models.TextField(blank=True)
    family_meaning = models.TextField(blank=True)
    relationship_meaning = models.TextField(blank=True)
    travel_meaning = models.TextField(blank=True)
    source_reference = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["fortune_set", "number"], name="unique_fortune_number_in_set")
        ]
        ordering = ["fortune_set", "number"]

    def __str__(self) -> str:
        return f"{self.fortune_set.code} #{self.number}"

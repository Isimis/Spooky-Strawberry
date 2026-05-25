from django.conf import settings
from django.db import models


class AIJob(models.Model):
    TYPE_PRODUCT_DESCRIPTION = "product_description"
    TYPE_PRODUCT_TAGS = "product_tags"
    TYPE_SEO = "seo"
    TYPE_ANALYSIS = "analysis"
    TYPE_IMAGE_BRIEF = "image_brief"

    STATUS_QUEUED = "queued"
    STATUS_RUNNING = "running"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"

    TYPE_CHOICES = [
        (TYPE_PRODUCT_DESCRIPTION, "Product description"),
        (TYPE_PRODUCT_TAGS, "Product tags"),
        (TYPE_SEO, "SEO"),
        (TYPE_ANALYSIS, "Analysis"),
        (TYPE_IMAGE_BRIEF, "Image brief"),
    ]

    STATUS_CHOICES = [
        (STATUS_QUEUED, "Queued"),
        (STATUS_RUNNING, "Running"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
    ]

    job_type = models.CharField(max_length=40, choices=TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_QUEUED)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="ai_jobs",
        null=True,
        blank=True,
    )
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.SET_NULL,
        related_name="ai_jobs",
        null=True,
        blank=True,
    )
    prompt = models.TextField(blank=True)
    input_data = models.JSONField(default=dict, blank=True)
    output_data = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.job_type} / {self.status}"


class AIContentSuggestion(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_ACCEPTED = "accepted"
    STATUS_REJECTED = "rejected"

    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_ACCEPTED, "Accepted"),
        (STATUS_REJECTED, "Rejected"),
    ]

    job = models.ForeignKey(
        AIJob,
        on_delete=models.CASCADE,
        related_name="suggestions",
    )
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.CASCADE,
        related_name="ai_suggestions",
        null=True,
        blank=True,
    )
    field_name = models.CharField(max_length=80)
    suggested_value = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="reviewed_ai_suggestions",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.field_name} suggestion"

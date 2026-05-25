from django.db import models


class CheckoutDraft(models.Model):
    STEP_CART = "cart"
    STEP_CUSTOMER = "customer"
    STEP_SHIPPING = "shipping"
    STEP_REVIEW = "review"

    STEP_CHOICES = [
        (STEP_CART, "Cart"),
        (STEP_CUSTOMER, "Customer"),
        (STEP_SHIPPING, "Shipping"),
        (STEP_REVIEW, "Review"),
    ]

    session_key = models.CharField(max_length=80, db_index=True)
    email = models.EmailField(blank=True)
    current_step = models.CharField(max_length=30, choices=STEP_CHOICES, default=STEP_CART)
    data = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Checkout draft {self.session_key}"

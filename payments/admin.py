from django.contrib import admin

from .models import PackagePaymentAttempt


@admin.register(PackagePaymentAttempt)
class PackagePaymentAttemptAdmin(admin.ModelAdmin):
    list_display = ("receipt", "user", "package", "amount_paise", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("receipt", "order_id", "payment_id", "user__username")

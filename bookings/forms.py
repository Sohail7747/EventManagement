from django import forms
from django.utils import timezone

from admin_panel.models import Profile
from .availability import (
    BookingUnavailableError,
    assert_dates_available,
    seller_ids_for_item,
)


class PackageBookingForm(forms.Form):
    guest_count = forms.IntegerField(
        min_value=1,
        max_value=500,
        initial=1,
        widget=forms.NumberInput(
            attrs={"class": "form-control", "min": 1, "max": 500},
        ),
    )
    booking_date = forms.DateField(
        widget=forms.DateInput(
            attrs={
                "type": "date",
                "class": "form-control booking-date-input",
            },
        ),
    )
    booking_end_date = forms.DateField(
        widget=forms.DateInput(
            attrs={"type": "date", "class": "form-control"},
        ),
    )
    customer_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(
            attrs={"class": "form-control", "autocomplete": "name"},
        ),
    )
    customer_email = forms.EmailField(
        widget=forms.EmailInput(
            attrs={"class": "form-control", "autocomplete": "email"},
        ),
    )
    customer_phone = forms.CharField(
        max_length=20,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "type": "tel",
                "autocomplete": "tel",
            },
        ),
    )
    customer_notes = forms.CharField(
        required=False,
        max_length=1000,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "Share any special requests (optional)",
            },
        ),
    )

    def __init__(
        self,
        *args,
        package,
        user,
        include_guest_count=True,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.package = package
        if not include_guest_count:
            self.fields.pop("guest_count")
        try:
            phone = user.profile.phone
        except Profile.DoesNotExist:
            phone = ""
        self.fields["customer_name"].initial = (
            user.get_full_name() or user.username
        )
        self.fields["customer_email"].initial = user.email
        self.fields["customer_phone"].initial = phone
        self.fields["booking_date"].widget.attrs["min"] = (
            timezone.localdate().isoformat()
        )
        self.fields["booking_end_date"].widget.attrs["min"] = (
            timezone.localdate().isoformat()
        )

    def clean_booking_date(self):
        booking_date = self.cleaned_data["booking_date"]
        if booking_date < timezone.localdate():
            raise forms.ValidationError("Choose today or a future date.")
        return booking_date

    def clean(self):
        cleaned_data = super().clean()
        if self.package.total_price < 0:
            raise forms.ValidationError(
                "This package has an invalid price and cannot be booked."
            )
        booking_date = cleaned_data.get("booking_date")
        booking_end_date = cleaned_data.get("booking_end_date")
        if booking_date and booking_end_date and booking_end_date < booking_date:
            self.add_error(
                "booking_end_date",
                "End date must be the same as or later than the start date.",
            )
        if booking_date and booking_end_date and booking_end_date >= booking_date:
            try:
                seller_ids = seller_ids_for_item(
                    "CATALOG_PACKAGE"
                    if hasattr(self.package, "package_items")
                    else "CUSTOM_PACKAGE",
                    self.package,
                )
                assert_dates_available(
                    seller_ids,
                    booking_date,
                    booking_end_date,
                )
            except BookingUnavailableError as error:
                self.add_error("booking_date", str(error))
        return cleaned_data
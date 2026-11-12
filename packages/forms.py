from django import forms
from django.db import transaction

from admin_panel.models import Event, Seller, Service
from .models import CatalogPackage, CatalogPackageItem


class CatalogPackageForm(forms.ModelForm):
    event = forms.ModelChoiceField(
        queryset=Event.objects.all().order_by("title"),
        empty_label="Select an event",
        widget=forms.RadioSelect,
        label="Choose one event"
    )

    seller = forms.ModelChoiceField(
        queryset=Seller.objects.select_related("user").order_by("business_name"),
        empty_label="Select a seller",
        widget=forms.RadioSelect,
        label="Choose one seller"
    )

    services = forms.ModelMultipleChoiceField(
        queryset=Service.objects.all().order_by("name"),
        widget=forms.CheckboxSelectMultiple,
        required=True,
        label="Choose services"
    )

    class Meta:
        model = CatalogPackage
        fields = ["title", "description", "event", "seller"]

        widgets = {
            "title": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Enter package title"
            }),
            "description": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Describe this package"
            }),
        }

    def save(self, commit=True):
        package = super().save(commit=commit)

        if commit:
            self.save_services(package)

        return package

    @transaction.atomic
    def save_services(self, package):
        selected_services = self.cleaned_data["services"]
        price_data = self.data

        package.package_items.all().delete()

        for service in selected_services:
            raw_price = price_data.get(f"price_{service.pk}", "").strip()

            if not raw_price:
                raise forms.ValidationError(
                    f"Please enter a price for {service.name}."
                )

            try:
                from decimal import Decimal, InvalidOperation
                price = Decimal(raw_price)
            except (InvalidOperation, ValueError):
                raise forms.ValidationError(
                    f"Enter a valid price for {service.name}."
                )

            if not price.is_finite() or price < 0:
                raise forms.ValidationError(
                    f"Price for {service.name} must be zero or greater."
                )

            CatalogPackageItem.objects.create(
                package=package,
                service=service,
                selected_price=price
            )

    def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.fields["services"].queryset = (
                Service.objects
                .select_related("seller")
                .order_by("name", "id")
                .distinct()
    )        
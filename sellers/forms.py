from django import forms
from django.db.models import Q
from dashboard.models import Event

from dashboard.models import Event, Service
from packages.models import CatalogPackage

class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = [
            "title",
            "description",
            "image",
        ]

        widgets = {
            "title": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Enter event title",
            }),
            "description": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "Describe your event",
            }),
            "image": forms.ClearableFileInput(attrs={
                "class": "form-control",
                "accept": "image/*",
            }),
        }

class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ["name", "description", "image", "price"]

        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Enter service name",
            }),
            "description": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "Describe your service",
            }),
            "image": forms.ClearableFileInput(attrs={
                "class": "form-control",
            }),
            "price": forms.NumberInput(attrs={
                "class": "form-control",
                "placeholder": "Enter price",
                "min": "0",
                "step": "0.01",
            }),
        }




class SellerCatalogPackageForm(forms.ModelForm):
    event = forms.ModelChoiceField(
        queryset=Event.objects.none(),
        empty_label="Choose your event",
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Event",
    )

    services = forms.ModelMultipleChoiceField(
        queryset=Service.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=True,
        label="Services",
    )

    class Meta:
        model = CatalogPackage
        fields = ["title", "description", "event"]
        widgets = {
            "title": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Enter package title",
            }),
            "description": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Describe your package",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        events = Event.objects.filter(
            seller__isnull=True,
            is_deleted=False,
        )
        if self.instance.pk:
            events = Event.objects.filter(
                Q(seller__isnull=True, is_deleted=False)
                | Q(catalog_packages=self.instance)
            )
        self.fields["event"].queryset = events.order_by("title").distinct()
        services = Service.objects.filter(
            seller__isnull=True,
            is_deleted=False,
        )
        if self.instance.pk:
            services = Service.objects.filter(
                Q(seller__isnull=True, is_deleted=False)
                | Q(catalog_package_items__package=self.instance)
            )
        self.fields["services"].queryset = services.order_by(
            "name"
        ).distinct()
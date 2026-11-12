
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm
from django.db import transaction

from .models import Seller, Event, Service, StaticPage


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Enter your username",
        })
    )

    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "class": "form-control",
            "placeholder": "Enter your password",
        })
    )


class SellerRegistrationForm(forms.Form):
    full_name = forms.CharField(max_length=150)
    username = forms.CharField(max_length=150)
    email = forms.EmailField()
    business_name = forms.CharField(max_length=200)
    phone = forms.CharField(max_length=15, required=False)
    address = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-control"}),
        required=False
    )
    password = forms.CharField(widget=forms.PasswordInput)
    ReEnter_password = forms.CharField(widget=forms.PasswordInput)

    def clean_username(self):
        username = self.cleaned_data["username"].strip()

        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("This username is already taken.")

        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("This email is already registered.")

        return email

    def clean(self):
        cleaned_data = super().clean()

        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("ReEnter_password")

        if password and confirm_password and password != confirm_password:
            self.add_error(
                "ReEnter_password",
                "Passwords do not match."
            )

        return cleaned_data

    @transaction.atomic
    def save(self):
        user = User.objects.create_user(
            username=self.cleaned_data["username"],
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password"],
            first_name=self.cleaned_data["full_name"],
        )

        Seller.objects.create(
            user=user,
            business_name=self.cleaned_data["business_name"],
            phone=self.cleaned_data["phone"],
            address=self.cleaned_data["address"],
        )

        return user


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = [
            "title",
            "description",
            "image",
            "location",
            "event_date",
        ]

        widgets = {
            "title": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Enter event name",
            }),
            "description": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 4,
            }),
            "image": forms.ClearableFileInput(attrs={
                "class": "form-control",
                "accept": "image/*",
            }),
            "location": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Enter event location",
            }),
            "event_date": forms.DateInput(attrs={
                "class": "form-control",
                "type": "date",
            }),

        }


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = [
            "name",
            "description",
            "image",
            ]

        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "e.g. Catering, Flowers, Photography",
            }),
            "description": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 3,
            }),
                "image": forms.ClearableFileInput(attrs={
                "class": "form-control",
                "accept": "image/*",
            }),
        }


class StaticPageForm(forms.ModelForm):
    class Meta:
        model = StaticPage
        fields = ["title", "slug", "content"]
        widgets = {
            "title": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Enter page title",
            }),
            "slug": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "page-url",
            }),
            "content": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 12,
            }),
        }

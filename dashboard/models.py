
from django.db import models
from django.contrib.auth.models import User
from django.conf import settings
from django.core.validators import MinValueValidator

class Profile(models.Model):
    ROLE_CHOICES = [
        ("SUB_ADMIN", "Sub-admin"),
        ("USER", "User"),
        ("SELLER", "Seller"),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile"
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default="USER"
    )
    phone = models.CharField(max_length=15, blank=True, default="")
    city = models.CharField(max_length=100, blank=True, default="")
    profile_photo = models.ImageField(
        upload_to="profiles/",
        blank=True,
        null=True
    )
    
    def __str__(self):
        return f"{self.user.username} - {self.role}"

class Seller(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="seller_profile"
    )
    business_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=15, blank=True)
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.business_name


class Event(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    is_deleted = models.BooleanField(default=False)
    location = models.CharField(max_length=200)
    event_date = models.DateField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(
        upload_to="events/",
        blank=True,
        null=True
    )
    seller = models.ForeignKey(
        Seller,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class Service(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField()
    is_deleted = models.BooleanField(default=False)

    image = models.ImageField(
        upload_to="services/",
        blank=True,
        null=True
    )

    price = models.DecimalField(max_digits=10, decimal_places=2)

    seller = models.ForeignKey(
        Seller,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="services"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name



class StaticPage(models.Model):
    title = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(unique=True)
    content = models.TextField()
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

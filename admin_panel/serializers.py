
from django.contrib.auth.models import User
from django.db import transaction
from rest_framework import serializers

from .models import Profile, Seller


class RegistrationSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=100)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=15, required=False, allow_blank=True)
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        trim_whitespace=False
    )
    role = serializers.ChoiceField(
        choices=["SUB_ADMIN", "USER", "SELLER"]
    )

    def validate_email(self, value):
        email = value.strip().lower()

        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError(
                "This email is already registered."
            )

        return email

    @transaction.atomic
    def create(self, validated_data):
        full_name = validated_data["full_name"].strip()
        email = validated_data["email"]
        password = validated_data["password"]
        role = validated_data["role"]
        phone = validated_data.get("phone", "")

        if not full_name:
            raise serializers.ValidationError({
                "full_name": "Full name is required."
            })

        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=full_name,
        )

        Profile.objects.create(
            user=user,
            role=role,
            phone=phone
        )

        if role == "SELLER":
            Seller.objects.create(
                user=user,
                business_name=full_name,
                phone=phone,
            )

        return user


from django.contrib.auth.models import User
from rest_framework import serializers
from .models import Profile

    #For user

class AdminUserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="first_name", max_length=150)
    phone = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        max_length=15
    )
    role = serializers.SerializerMethodField()
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        required=False,
        trim_whitespace=False
    )

    class Meta:
        model = User
        fields = [
            "id", "full_name", "email", "phone",
            "password", "role", "is_active"
        ]
        read_only_fields = ["id", "role"]

    def validate_email(self, value):
        email = value.strip().lower()
        matches = User.objects.filter(email__iexact=email)

        if self.instance:
            matches = matches.exclude(pk=self.instance.pk)

        if matches.exists():
            raise serializers.ValidationError(
                "This email is already registered."
            )

        return email

    def validate(self, attrs):
        if self.instance is None and not attrs.get("password"):
            raise serializers.ValidationError({
                "password": "Password is required."
            })

        if not attrs.get("first_name", "").strip():
            raise serializers.ValidationError({
                "full_name": "Full name is required."
            })

        return attrs

    def get_role(self, obj):
        if obj.is_superuser:
            return "ADMIN"
        if hasattr(obj, "profile"):
            return obj.profile.role
        return "UNASSIGNED"

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["phone"] = (
            instance.profile.phone
            if hasattr(instance, "profile")
            else ""
        )
        return data

    @transaction.atomic
    def create(self, validated_data):
        password = validated_data.pop("password")
        phone = validated_data.pop("phone", "")
        email = validated_data["email"].strip().lower()
        full_name = validated_data["first_name"].strip()

        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=full_name,
        )

        Profile.objects.create(
            user=user,
            role="USER",
            phone=phone,
        )
        return user

    @transaction.atomic
    def update(self, instance, validated_data):
        phone = validated_data.pop("phone", None)
        password = validated_data.pop("password", None)

        for field, value in validated_data.items():
            setattr(instance, field, value)

        instance.username = instance.email.strip().lower()

        if password:
            instance.set_password(password)

        instance.save()

        if phone is not None:
            Profile.objects.update_or_create(
                user=instance,
                defaults={"phone": phone}
            )

        return instance

    #For Seller


from django.contrib.auth.models import User
from django.db import transaction
from rest_framework import serializers

from .models import Seller, Profile

class AdminSellerSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(write_only=True)
    user_email = serializers.EmailField(
        source="user.email",
        read_only=True
    )
    password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        trim_whitespace=False
    )

    class Meta:
        model = Seller
        fields = [
            "id",
            "user_email",
            "email",
            "password",
            "business_name",
            "phone",
            "address",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password", "")

        if email:
            existing_email = User.objects.filter(
                email__iexact=email
            )

            existing_username = User.objects.filter(
                username__iexact=email
            )

            if self.instance:
                existing_email = existing_email.exclude(
                    pk=self.instance.user_id
                )
                existing_username = existing_username.exclude(
                    pk=self.instance.user_id
                )

            if existing_email.exists():
                raise serializers.ValidationError({
                    "email": "This email is already registered."
                })

            if existing_username.exists():
                raise serializers.ValidationError({
                    "email": "This email conflicts with an existing username."
                })

        if not self.instance and not password:
            raise serializers.ValidationError({
                "password": "Password is required when creating a seller."
            })

        if password and len(password) < 8:
            raise serializers.ValidationError({
                "password": "Password must contain at least 8 characters."
            })

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        email = validated_data.pop("email").strip().lower()
        password = validated_data.pop("password")

        business_name = validated_data.get("business_name", "")
        phone = validated_data.get("phone", "")

        # Create the seller's login account securely.
        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=business_name,
        )

        # Assign the SELLER role.
        Profile.objects.create(
            user=user,
            role="SELLER",
            phone=phone,
        )

        # Create the seller's business profile.
        seller = Seller.objects.create(
            user=user,
            **validated_data
        )

        return seller

    @transaction.atomic
    def update(self, instance, validated_data):
        email = validated_data.pop("email", None)
        password = validated_data.pop("password", "")

        # Update the login email when provided.
        if email:
            email = email.strip().lower()
            instance.user.email = email
            instance.user.username = email

        # Update password only when the admin entered a new one.
        if password:
            instance.user.set_password(password)

        if email or password:
            instance.user.save()

        # Update business profile fields.
        for field, value in validated_data.items():
            setattr(instance, field, value)

        instance.save()

        # Keep the seller's profile phone number synchronized.
        if "phone" in validated_data:
            Profile.objects.filter(
                user=instance.user
            ).update(phone=instance.phone)

        # Keep the displayed account name synchronized.
        if "business_name" in validated_data:
            instance.user.first_name = instance.business_name
            instance.user.save(update_fields=["first_name"])

        return instance

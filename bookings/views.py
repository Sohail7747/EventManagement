
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Avg, Count, Prefetch, Q
from django.http import JsonResponse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_time

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from django.contrib.auth.models import User
from admin_panel.models import Event, Service, Profile
from packages.models import CatalogPackage, EventPackage

from .models import (
    Booking,
    BookingSellerDecision,
    EventReview,
    Favourite,
    ServiceReview,
    ensure_booking_seller_decisions,
)
from .serializers import BookingSerializer, FavouriteSerializer
from packages.pricing import PACKAGE_GUEST_PRICE
from payments.models import BookingCancellationRequest
from .availability import (
    BookingUnavailableError,
    release_booking_reservations,
    reserve_booking_dates,
    seller_ids_for_item,
)
from .models import BookingDateReservation, PackageReview, SellerUnavailableDate
from .notifications import send_booking_email


# =========================================================
# CUSTOMER ACCESS HELPERS
# =========================================================

def is_regular_user(user):
    if not user.is_authenticated:
        return False

    try:
        return user.profile.role == "USER"
    except Exception:
        return False


def customer_required(request):
    if not is_regular_user(request.user):
        return Response(
            {"error": "This feature is available to customer accounts only."},
            status=status.HTTP_403_FORBIDDEN,
        )
    return None


def customer_page_access(request):
    """
    Protect customer HTML pages from seller, sub-admin,
    and other non-customer accounts.
    """
    if not is_regular_user(request.user):
        messages.error(
            request,
            "This section is available to customer accounts only.",
        )
        return redirect("home")

    return None


def get_customer_bookings(user):
    return Booking.objects.filter(user=user).select_related(
        "event",
        "service",
        "catalog_package",
        "package_event",
        "seller",
        "seller__user",
        "custom_package",
        "custom_package__event",
        "payment_attempt",
    ).prefetch_related("package_services")


def get_customer_favourites(user):
    return Favourite.objects.filter(user=user).exclude(
        catalog_package__is_deleted=True
    ).exclude(
        service__is_deleted=True
    ).select_related(
        "event",
        "service",
        "catalog_package",
    )


# =========================================================
# CUSTOMER DASHBOARD HTML PAGES
# =========================================================

def package_detail_page(request, package_id):
    services_with_reviews = (
        Service.objects.annotate(
            rating_average=Avg("reviews__rating"),
            review_count=Count("reviews", distinct=True),
        )
        .prefetch_related(
            Prefetch(
                "reviews",
                queryset=ServiceReview.objects.select_related("user").order_by(
                    "-created_at"
                ),
            )
        )
    )
    package = get_object_or_404(
        CatalogPackage.objects
        .filter(is_deleted=False)
        .exclude(event__is_deleted=True)
        .exclude(package_items__service__is_deleted=True)
        .annotate(
            rating_average=Avg("reviews__rating"),
            review_count=Count("reviews", distinct=True),
        )
        .select_related("event", "seller", "seller__user")
        .prefetch_related(
            Prefetch(
                "package_items__service",
                queryset=services_with_reviews,
            )
        ),
        pk=package_id,
    )
    can_favourite = is_regular_user(request.user)
    favourite_package_ids = set()
    if can_favourite and Favourite.objects.filter(
        user=request.user,
        catalog_package=package,
    ).exists():
        favourite_package_ids.add(package.pk)

    return render(
        request,
        "bookings/package_detail.html",
        {
            "package": package,
            "can_favourite": can_favourite,
            "favourite_package_ids": favourite_package_ids,
            "guest_price": PACKAGE_GUEST_PRICE,
            "starting_price": package.total_price + PACKAGE_GUEST_PRICE,
            "reviews": package.reviews.select_related("user").all(),
        },
    )


@login_required(login_url="/accounts/login/")
def user_dashboard_page(request):
    denied = customer_page_access(request)
    if denied:
        return denied

    bookings = get_customer_bookings(request.user)
    favourites = get_customer_favourites(request.user)

    context = {
        "total_bookings": bookings.count(),
        "pending_bookings": bookings.filter(
            status=Booking.Status.PENDING
        ).count(),
        "confirmed_bookings": bookings.filter(
            status=Booking.Status.CONFIRMED
        ).count(),
        "total_favourites": favourites.count(),
        "recent_bookings": bookings[:5],
        "active_page": "dashboard",
    }

    return render(
        request,
        "bookings/user_dashboard.html",
        context,
    )


@login_required(login_url="/accounts/login/")
def my_bookings_page(request):
    denied = customer_page_access(request)
    if denied:
        return denied

    all_bookings = get_customer_bookings(request.user)

    selected_status = request.GET.get("status", "").strip().upper()

    valid_statuses = [
        choice[0] for choice in Booking.Status.choices
    ]

    bookings = all_bookings

    if selected_status in valid_statuses:
        bookings = bookings.filter(status=selected_status)
    else:
        selected_status = ""

    context = {
        "bookings": bookings,
        "total_bookings": all_bookings.count(),
        "pending_bookings": all_bookings.filter(
            status=Booking.Status.PENDING
        ).count(),
        "confirmed_bookings": all_bookings.filter(
            status=Booking.Status.CONFIRMED
        ).count(),
        "cancelled_bookings": all_bookings.filter(
            status=Booking.Status.CANCELLED
        ).count(),
        "selected_status": selected_status,
        "status_choices": Booking.Status.choices,
        "active_page": "bookings",
    }

    return render(
        request,
        "bookings/my_bookings.html",
        context,
    )


@login_required(login_url="/accounts/login/")
def booking_detail_page(request, pk):
    denied = customer_page_access(request)
    if denied:
        return denied

    booking = get_object_or_404(
        get_customer_bookings(request.user),
        pk=pk,
    )
    seller_decisions = list(
        booking.seller_decisions.select_related("seller").order_by("seller_id")
    )
    event_end_date = booking.booking_end_date or booking.booking_date
    seller_has_reported_completion = bool(seller_decisions) and any(
        decision.status == BookingSellerDecision.Status.ACCEPTED
        and decision.seller_completed_at is not None
        for decision in seller_decisions
    )
    can_confirm_completion = (
        booking.status == Booking.Status.CONFIRMED
        and booking.customer_confirmed_at is None
        and seller_has_reported_completion
    )
    has_package_review = PackageReview.objects.filter(booking=booking).exists()
    has_event_review = EventReview.objects.filter(booking=booking).exists()
    has_service_reviews = booking.service_reviews.exists()
    reviewable_booking = booking.item_type in (
        Booking.ItemType.EVENT,
        Booking.ItemType.SERVICE,
        Booking.ItemType.CATALOG_PACKAGE,
        Booking.ItemType.CUSTOM_PACKAGE,
    )
    completion_confirmed = (
        booking.status == Booking.Status.COMPLETED
        or (
            booking.status == Booking.Status.CONFIRMED
            and booking.customer_confirmed_at is not None
        )
    )

    return render(
        request,
        "bookings/booking_detail.html",
        {
            "booking": booking,
            "seller_decisions": seller_decisions,
            "can_confirm_completion": can_confirm_completion,
            "seller_has_reported_completion": seller_has_reported_completion,
            "event_has_ended": event_end_date <= timezone.localdate(),
            "cancellation_request": booking.cancellation_requests.first(),
            "can_review_booking": (
                reviewable_booking
                and completion_confirmed
                and not has_package_review
                and not has_event_review
                and not has_service_reviews
            ),
            "completion_confirmed": completion_confirmed,
            "review_submitted": (
                has_package_review or has_event_review or has_service_reviews
            ),
            "can_request_cancellation": (
                booking.status == Booking.Status.PENDING
                or (
                    booking.status == Booking.Status.CONFIRMED
                    and booking.customer_confirmed_at is None
                )
            ),
            "active_page": "bookings",
        },
    )


@login_required(login_url="/accounts/login/")
@require_POST
def submit_package_review(request, pk):
    denied = customer_page_access(request)
    if denied:
        return denied
    with transaction.atomic():
        booking = get_object_or_404(
            Booking.objects.select_for_update().filter(
                Q(status=Booking.Status.COMPLETED)
                | Q(
                    status=Booking.Status.CONFIRMED,
                    customer_confirmed_at__isnull=False,
                )
            ),
            pk=pk,
            user=request.user,
            item_type__in=[
                Booking.ItemType.EVENT,
                Booking.ItemType.SERVICE,
                Booking.ItemType.CATALOG_PACKAGE,
                Booking.ItemType.CUSTOM_PACKAGE,
            ],
        )
        if (
            PackageReview.objects.filter(booking=booking).exists()
            or EventReview.objects.filter(booking=booking).exists()
            or booking.service_reviews.exists()
        ):
            messages.error(request, "You have already reviewed this package.")
            return redirect("booking-detail", pk=booking.pk)
        try:
            rating = int(request.POST.get("rating", ""))
        except (TypeError, ValueError):
            rating = 0
        comment = request.POST.get("comment", "").strip()
        if rating not in range(1, 6):
            messages.error(request, "Choose a rating from 1 to 5 stars.")
            return redirect("booking-detail", pk=booking.pk)
        if len(comment) > 2000:
            messages.error(request, "Your review must be 2,000 characters or fewer.")
            return redirect("booking-detail", pk=booking.pk)
        service_ids = list(
            booking.package_services.values_list("pk", flat=True)
        )
        if booking.item_type == Booking.ItemType.SERVICE:
            service_ids = [booking.service_id] if booking.service_id else []
        elif not service_ids and booking.item_type == Booking.ItemType.CATALOG_PACKAGE:
            service_ids = list(
                booking.catalog_package.package_items.values_list(
                    "service_id",
                    flat=True,
                )
            )
        elif not service_ids and booking.item_type == Booking.ItemType.CUSTOM_PACKAGE:
            service_ids = list(
                booking.custom_package.package_services.values_list(
                    "service_id",
                    flat=True,
                )
            )
        if booking.item_type != Booking.ItemType.EVENT and not service_ids:
            messages.error(
                request,
                "This booking has no services available to review.",
            )
            return redirect("booking-detail", pk=booking.pk)

        if booking.item_type == Booking.ItemType.CATALOG_PACKAGE:
            PackageReview.objects.create(
                package=booking.catalog_package,
                booking=booking,
                user=request.user,
                rating=rating,
                comment=comment,
            )
        elif booking.item_type == Booking.ItemType.EVENT:
            EventReview.objects.create(
                event=booking.event,
                booking=booking,
                user=request.user,
                rating=rating,
                comment=comment,
            )
        if service_ids:
            ServiceReview.objects.bulk_create(
                [
                    ServiceReview(
                        booking=booking,
                        service_id=service_id,
                        user=request.user,
                        rating=rating,
                        comment=comment,
                    )
                    for service_id in service_ids
                ]
            )
    messages.success(request, "Thanks for sharing your booking review.")
    return redirect("booking-detail", pk=booking.pk)


@login_required(login_url="/accounts/login/")
@require_POST
def cancel_booking_page(request, pk):
    denied = customer_page_access(request)
    if denied:
        return denied

    booking = get_object_or_404(Booking, pk=pk, user=request.user)
    reason = request.POST.get("reason", "").strip()
    if not reason:
        messages.error(request, "Please tell us why you are requesting cancellation.")
        return redirect("booking-detail", pk=booking.pk)
    try:
        cancellation = create_cancellation_request(booking, request.user, reason)
    except ValueError as error:
        messages.error(request, str(error))
        return redirect("booking-detail", pk=booking.pk)
    messages.success(
        request,
        "Your cancellation request was sent for admin review.",
    )

    return redirect("booking-detail", pk=booking.pk)


def create_cancellation_request(booking, user, reason):
    with transaction.atomic():
        booking = Booking.objects.select_for_update().get(pk=booking.pk)
        if booking.status not in (
            Booking.Status.PENDING,
            Booking.Status.CONFIRMED,
        ) or booking.customer_confirmed_at is not None:
            raise ValueError(
                "This booking cannot be cancelled in its current status."
            )
        if booking.cancellation_requests.filter(
            status__in=[
                BookingCancellationRequest.Status.REQUESTED,
                BookingCancellationRequest.Status.PROCESSING,
                BookingCancellationRequest.Status.FAILED,
            ]
        ).exists():
            raise ValueError("A cancellation request is already being reviewed.")
        payment_attempt = getattr(booking, "payment_attempt", None)
        refund_amount = (
            payment_attempt.total_price
            if payment_attempt
            and payment_attempt.status == "PAID"
            else 0
        )
        cancellation = BookingCancellationRequest.objects.create(
            booking=booking,
            requested_by=user,
            reason=reason[:1000],
            refund_amount=refund_amount,
        )
        transaction.on_commit(
            lambda booking_id=booking.pk: send_booking_email(
                Booking.objects.select_related("user").get(pk=booking_id),
                "Cancellation request received",
                f"We received your cancellation request for booking #{booking.pk}. "
                "Our team will review it and email you with the outcome.",
            )
        )
        return cancellation

@login_required(login_url="/accounts/login/")
@require_POST
def confirm_booking_completion(request, pk):
    denied = customer_page_access(request)
    if denied:
        return denied

    with transaction.atomic():
        booking = get_object_or_404(
            Booking.objects.select_for_update(),
            pk=pk,
            user=request.user,
        )
        if (
            booking.status != Booking.Status.CONFIRMED
            or booking.customer_confirmed_at is not None
        ):
            messages.error(
                request,
                "This booking is not awaiting your completion confirmation.",
            )
            return redirect("booking-detail", pk=booking.pk)

        event_end_date = booking.booking_end_date or booking.booking_date
        if event_end_date >= timezone.localdate():
            messages.error(
                request,
                "You can confirm completion after the event has ended.",
            )
            return redirect("booking-detail", pk=booking.pk)

        decisions = list(
            booking.seller_decisions.select_for_update().order_by("seller_id")
        )
        if not decisions or any(
            decision.status != BookingSellerDecision.Status.ACCEPTED
            or decision.seller_completed_at is None
            for decision in decisions
        ):
            messages.error(
                request,
                "Each seller must report the event complete before you can confirm it.",
            )
            return redirect("booking-detail", pk=booking.pk)

        booking.customer_confirmed_at = timezone.now()
        booking.customer_completion_rejected_at = None
        booking.customer_completion_rejection_reason = ""
        booking.save(
            update_fields=[
                "customer_confirmed_at",
                "customer_completion_rejected_at",
                "customer_completion_rejection_reason",
                "updated_at",
            ]
        )

    messages.success(
        request,
        "Your completion confirmation has been sent to the admin for final payout approval.",
    )
    return redirect("booking-detail", pk=pk)


@login_required(login_url="/accounts/login/")
@require_POST
def reject_booking_completion(request, pk):
    denied = customer_page_access(request)
    if denied:
        return denied

    with transaction.atomic():
        booking = get_object_or_404(
            Booking.objects.select_for_update(),
            pk=pk,
            user=request.user,
        )
        if (
            booking.status != Booking.Status.CONFIRMED
            or booking.customer_confirmed_at is not None
        ):
            messages.error(
                request,
                "This booking is not currently awaiting your completion decision.",
            )
            return redirect("booking-detail", pk=booking.pk)

        reason = request.POST.get("rejection_reason", "").strip()
        proof_file = request.FILES.get("rejection_proof")

        if not reason:
            messages.error(
                request,
                "Please describe why the event was not completed.",
            )
            return redirect("booking-detail", pk=booking.pk)

        booking.customer_completion_rejected_at = timezone.now()
        booking.customer_completion_rejection_reason = reason
        if proof_file:
            booking.customer_completion_proof = proof_file

        booking.save()

    messages.warning(
        request,
        "You have reported this event as not completed. Your proof and reason have been submitted for admin and seller review.",
    )
    return redirect("booking-detail", pk=pk)


@login_required(login_url="/accounts/login/")
def my_favourites_page(request):
    denied = customer_page_access(request)
    if denied:
        return denied

    all_favourites = get_customer_favourites(request.user)

    selected_type = (
        request.GET.get("type", "").strip().upper()
    )

    favourites = all_favourites

    if selected_type == "EVENT":
        favourites = favourites.filter(event__isnull=False)
    elif selected_type == "SERVICE":
        favourites = favourites.filter(service__isnull=False)
    elif selected_type == "CATALOG_PACKAGE":
        favourites = favourites.filter(
            catalog_package__isnull=False
        )
    else:
        selected_type = ""

    context = {
        "favourites": favourites,
        "favourite_event_count": all_favourites.filter(
            event__isnull=False
        ).count(),
        "favourite_service_count": all_favourites.filter(
            service__isnull=False
        ).count(),
        "favourite_package_count": all_favourites.filter(
            catalog_package__isnull=False
        ).count(),
        "selected_type": selected_type,
        "active_page": "favourites",
    }

    return render(
        request,
        "bookings/my_favourites.html",
        context,
    )


@login_required(login_url="/accounts/login/")
@require_POST
def remove_favourite_page(request, pk):
    denied = customer_page_access(request)
    if denied:
        return denied

    favourite = get_object_or_404(
        Favourite,
        pk=pk,
        user=request.user,
    )

    favourite.delete()

    messages.success(request, "Item removed from your favourites.")

    return redirect("my-favourites")


@login_required(login_url="/accounts/login/")
@require_POST
def toggle_package_favourite(request, package_id):
    denied = customer_page_access(request)
    if denied:
        return denied

    package = get_object_or_404(
        CatalogPackage.objects
        .filter(is_deleted=False)
        .exclude(event__is_deleted=True)
        .exclude(package_items__service__is_deleted=True),
        pk=package_id,
    )
    favourite, created = Favourite.objects.get_or_create(
        user=request.user,
        catalog_package=package,
    )
    if created:
        message = "Package added to your favourites."
    else:
        favourite.delete()
        message = "Package removed from your favourites."

    next_url = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        next_url = reverse("public-packages")

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({
            "is_favourite": created,
            "message": message,
            "favourites_url": reverse("my-favourites"),
        })

    messages.success(request, message)
    return redirect(next_url)


@login_required(login_url="/accounts/login/")
def user_profile_page(request):
    denied = customer_page_access(request)
    if denied:
        return denied

    profile = getattr(request.user, "profile", None)
    if not profile:
        profile, _ = Profile.objects.get_or_create(
            user=request.user,
            defaults={"role": "USER"}
        )

    if request.method == "POST":
        full_name = request.POST.get("full_name", "").strip()
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        email = request.POST.get("email", "").strip()
        phone = request.POST.get("phone", "").strip()
        city = request.POST.get("city", "").strip()

        if not full_name and (first_name or last_name):
            full_name = f"{first_name} {last_name}".strip()
        elif full_name:
            if " " in full_name:
                first_name, last_name = full_name.split(" ", 1)
            else:
                first_name, last_name = full_name, ""

        if not full_name and not first_name:
            messages.error(request, "Full name is required.")

        elif not email:
            messages.error(request, "Email address is required.")

        else:
            try:
                validate_email(email)
            except ValidationError:
                messages.error(
                    request,
                    "Please enter a valid email address.",
                )
            else:
                if User.objects.filter(email__iexact=email).exclude(pk=request.user.pk).exists():
                    messages.error(
                        request,
                        "This email address is already in use by another account.",
                    )
                else:
                    request.user.first_name = first_name
                    request.user.last_name = last_name
                    request.user.email = email
                    request.user.save(
                        update_fields=[
                            "first_name",
                            "last_name",
                            "email",
                        ]
                    )

                    profile.city = city
                    if phone:
                        profile.phone = phone

                    if "profile_photo" in request.FILES:
                        photo = request.FILES["profile_photo"]
                        if photo.size > 4 * 1024 * 1024:
                            messages.error(
                                request,
                                "Profile photo must be less than 4 MB.",
                            )
                            return redirect("user-profile")
                        profile.profile_photo = photo

                    profile.save()

                    messages.success(
                        request,
                        "Your profile has been updated successfully.",
                    )

                    return redirect("user-profile")

    context = {
        "profile": profile,
        "profile_phone": profile.phone or "",
        "profile_city": getattr(profile, "city", "") or "",
        "profile_photo": profile.profile_photo if getattr(profile, "profile_photo", None) else None,
        "user_full_name": request.user.get_full_name() or request.user.username,
        "active_page": "profile",
    }

    return render(
        request,
        "bookings/user_profile.html",
        context,
    )


# =========================================================
# BOOKING REST API
# =========================================================

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def bookings_api(request):
    denied = customer_required(request)
    if denied:
        return denied

    if request.method == "GET":
        bookings = Booking.objects.filter(user=request.user)
        serializer = BookingSerializer(
            bookings,
            many=True,
            context={"request": request},
        )
        return Response(serializer.data)

    item_type = request.data.get("item_type", "").strip().upper()
    item_id = request.data.get("item_id")
    date_value = request.data.get("booking_date")
    end_date_value = request.data.get("booking_end_date")
    time_value = request.data.get("booking_time")
    guest_count_value = request.data.get("guest_count", 1)
    customer_notes = request.data.get("customer_notes", "")

    if request.data.get("add_on_services"):
        return Response(
            {"error": "Package bookings no longer support add-on services."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not item_type or not item_id or not date_value:
        return Response(
            {
                "error": (
                    "item_type, item_id and booking_date are required."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    booking_date = parse_date(str(date_value))
    if not booking_date:
        return Response(
            {"error": "Use booking_date in YYYY-MM-DD format."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    booking_end_date = (
        parse_date(str(end_date_value))
        if end_date_value
        else None
    )
    if end_date_value and not booking_end_date:
        return Response(
            {"error": "Use booking_end_date in YYYY-MM-DD format."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if booking_end_date and booking_end_date < booking_date:
        return Response(
            {"error": "Booking end date cannot be before the start date."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if booking_date < timezone.localdate():
        return Response(
            {"error": "Booking date cannot be in the past."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    booking_time = parse_time(str(time_value)) if time_value else None
    if time_value and not booking_time:
        return Response(
            {"error": "Use booking_time in HH:MM format."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if (
        booking_date == timezone.localdate()
        and booking_time
        and booking_time
        <= timezone.localtime().time().replace(
            second=0,
            microsecond=0,
            tzinfo=None,
        )
    ):
        return Response(
            {"error": "Booking time must be later than the current time."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not isinstance(customer_notes, str):
        return Response(
            {"error": "customer_notes must be text."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        guest_count = int(guest_count_value)
    except (TypeError, ValueError):
        return Response(
            {"error": "guest_count must be an integer between 1 and 500."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if (
        isinstance(guest_count_value, bool)
        or guest_count < 1
        or guest_count > 500
    ):
        return Response(
            {"error": "guest_count must be an integer between 1 and 500."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    item = None
    event = None
    service = None
    catalog_package = None
    custom_package = None
    booking_seller = None

    if item_type == "EVENT":
        item = get_object_or_404(Event, pk=item_id, is_deleted=False)
        event = item
        booking_seller = item.seller
        item_title = item.title
        total_price = item.price

    elif item_type == "SERVICE":
        item = get_object_or_404(
            Service,
            pk=item_id,
            is_deleted=False,
        )
        service = item
        booking_seller = item.seller
        item_title = item.name
        total_price = item.price

    elif item_type == "CATALOG_PACKAGE":
        item = get_object_or_404(
            CatalogPackage.objects
            .filter(is_deleted=False)
            .exclude(event__is_deleted=True)
            .exclude(package_items__service__is_deleted=True)
            .select_related("event", "seller")
            .prefetch_related("package_items__service"),
            pk=item_id,
        )
        catalog_package = item
        booking_seller = item.seller
        item_title = item.title
        if item.total_price < 0 or item.event.price < 0:
            return Response(
                {"error": "This package does not have a valid price."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        total_price = (
            item.total_price
            + PACKAGE_GUEST_PRICE * guest_count
        )

    elif item_type == "CUSTOM_PACKAGE":
        item = get_object_or_404(
            EventPackage.objects.select_related("event"),
            pk=item_id,
            user=request.user,
        )
        custom_package = item
        item_title = (
            item.package_title or "My package"
        )
        total_price = item.total_cost

    else:
        return Response(
            {
                "error": (
                    "item_type must be EVENT, SERVICE, "
                    "CATALOG_PACKAGE or CUSTOM_PACKAGE."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if total_price is None or total_price < 0:
        return Response(
            {"error": "This item does not have a valid price."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        with transaction.atomic():
            booking = Booking.objects.create(
                user=request.user,
                item_type=item_type,
                event=event,
                service=service,
                catalog_package=catalog_package,
                package_event=(
                    catalog_package.event if catalog_package else None
                ),
                seller=booking_seller,
                custom_package=custom_package,
                booking_date=booking_date,
                booking_end_date=booking_end_date,
                booking_time=booking_time,
                guest_count=guest_count,
                total_price=total_price,
                item_title=item_title,
                customer_notes=customer_notes.strip(),
            )
            if catalog_package:
                booking.package_services.set(
                    catalog_package.package_items.values_list(
                        "service_id",
                        flat=True,
                    )
                )
            ensure_booking_seller_decisions(booking)
            reserve_booking_dates(
                seller_ids_for_item(item_type, item),
                booking_date,
                booking_end_date or booking_date,
                booking=booking,
            )
    except BookingUnavailableError as error:
        return Response(
            {"error": str(error)},
            status=status.HTTP_409_CONFLICT,
        )

    return Response(
        BookingSerializer(
            booking,
            context={"request": request},
        ).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def booking_detail_api(request, pk):
    denied = customer_required(request)
    if denied:
        return denied

    booking = get_object_or_404(
        Booking,
        pk=pk,
        user=request.user,
    )

    return Response(
        BookingSerializer(
            booking,
            context={"request": request},
        ).data
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def cancel_booking_api(request, pk):
    denied = customer_required(request)
    if denied:
        return denied

    booking = get_object_or_404(
        Booking,
        pk=pk,
        user=request.user,
    )

    reason = str(request.data.get("reason", "")).strip()
    if not reason:
        return Response(
            {"error": "A cancellation reason is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        create_cancellation_request(booking, request.user, reason)
    except ValueError as error:
        return Response(
            {"error": str(error)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    booking.refresh_from_db()
    return Response(
        BookingSerializer(
            booking,
            context={"request": request},
        ).data
    )


# =========================================================
# FAVOURITES REST API
# =========================================================

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def favourites_api(request):
    denied = customer_required(request)
    if denied:
        return denied

    if request.method == "GET":
        favourites = Favourite.objects.filter(user=request.user)

        return Response(
            FavouriteSerializer(
                favourites,
                many=True,
                context={"request": request},
            ).data
        )

    item_type = request.data.get("item_type", "").strip().upper()
    item_id = request.data.get("item_id")

    if not item_type or not item_id:
        return Response(
            {"error": "item_type and item_id are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if item_type == "EVENT":
        item = get_object_or_404(Event, pk=item_id, is_deleted=False)
        favourite, created = Favourite.objects.get_or_create(
            user=request.user,
            event=item,
        )

    elif item_type == "SERVICE":
        item = get_object_or_404(
            Service,
            pk=item_id,
            is_deleted=False,
        )
        favourite, created = Favourite.objects.get_or_create(
            user=request.user,
            service=item,
        )

    elif item_type == "CATALOG_PACKAGE":
        item = get_object_or_404(
            CatalogPackage,
            pk=item_id,
            is_deleted=False,
            event__is_deleted=False,
        )
        if item.package_items.filter(service__is_deleted=True).exists():
            return Response(
                {"error": "This package is not currently available."},
                status=status.HTTP_404_NOT_FOUND,
            )
        favourite, created = Favourite.objects.get_or_create(
            user=request.user,
            catalog_package=item,
        )

    else:
        return Response(
            {
                "error": (
                    "item_type must be EVENT, SERVICE "
                    "or CATALOG_PACKAGE."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        FavouriteSerializer(
            favourite,
            context={"request": request},
        ).data,
        status=(
            status.HTTP_201_CREATED
            if created
            else status.HTTP_200_OK
        ),
    )


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def remove_favourite_api(request, pk):
    denied = customer_required(request)
    if denied:
        return denied

    favourite = get_object_or_404(
        Favourite,
        pk=pk,
        user=request.user,
    )
    favourite.delete()

    return Response(status=status.HTTP_204_NO_CONTENT)

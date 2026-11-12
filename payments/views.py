import hashlib
import hmac
import json
import logging
import uuid
import calendar
from datetime import date
from decimal import Decimal

import razorpay
import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test
from django.db import transaction
from django.db.models import F, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_date
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from bookings.forms import PackageBookingForm
from bookings.models import (
    Booking,
    BookingDateReservation,
    BookingSellerDecision,
    SellerUnavailableDate,
    ensure_booking_seller_decisions,
)
from bookings.availability import (
    BookingUnavailableError,
    attach_reservations_to_booking,
    release_booking_reservations,
    reserve_booking_dates,
    seller_ids_for_item,
    unavailable_dates_for_sellers,
)
from bookings.notifications import send_booking_email
from packages.models import EventPackage
from dashboard.models import Profile, Seller
from dashboard.analytics import monthly_amounts
from packages.models import CatalogPackage
from packages.pricing import PACKAGE_GUEST_PRICE

from .models import (
    BookingCancellationRequest,
    PackagePaymentAttempt,
    PayoutRequest,
    SellerEarning,
)
from .settlements import create_booking_earnings


logger = logging.getLogger(__name__)
RAZORPAY_API_ERRORS = (
    razorpay.errors.BadRequestError,
    razorpay.errors.GatewayError,
    razorpay.errors.ServerError,
    requests.exceptions.RequestException,
)


def razorpay_client():
    return razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )


def is_regular_user(user):
    if not user.is_authenticated:
        return False
    try:
        return user.profile.role == "USER"
    except Profile.DoesNotExist:
        return False


def package_booking_context(package, form, payment_options=None):
    starting_price = package.total_price + PACKAGE_GUEST_PRICE
    availability_route = (
        "package-availability"
        if isinstance(package, CatalogPackage)
        else "custom-package-availability"
    )
    return {
        "package": package,
        "form": form,
        "today": timezone.localdate(),
        "guest_price": PACKAGE_GUEST_PRICE,
        "starting_price": starting_price,
        "payment_options": payment_options,
        "availability_url": reverse(
            availability_route,
            args=[package.pk],
        ),
    }


def complete_package_payment(attempt_id, payment):
    with transaction.atomic():
        attempt = PackagePaymentAttempt.objects.select_for_update().get(
            pk=attempt_id
        )
        payment_id = str(payment["id"])
        if attempt.status == PackagePaymentAttempt.Status.PAID:
            if attempt.payment_id != payment_id or not attempt.booking_id:
                raise ValueError("Payment attempt was already completed.")
            return attempt.booking

        if attempt.status != PackagePaymentAttempt.Status.CREATED:
            raise ValueError("This payment attempt is no longer active.")
        if (
            str(payment.get("order_id")) != attempt.order_id
            or payment.get("status") != "captured"
            or int(payment.get("amount", -1)) != attempt.amount_paise
            or payment.get("currency") != "INR"
        ):
            raise ValueError("Payment details do not match this order.")

        if attempt.package_id:
            booking = Booking.objects.create(
                user=attempt.user,
                item_type=Booking.ItemType.CATALOG_PACKAGE,
                catalog_package=attempt.package,
                package_event=attempt.package.event,
                seller=attempt.package.seller,
                booking_date=attempt.booking_date,
                booking_end_date=attempt.booking_end_date,
                guest_count=attempt.guest_count,
                customer_name=attempt.customer_name,
                customer_email=attempt.customer_email,
                customer_phone=attempt.customer_phone,
                total_price=attempt.total_price,
                item_title=attempt.package.title,
                customer_notes=attempt.customer_notes,
            )
            booking.package_services.set(
                attempt.package.package_items.values_list(
                    "service_id",
                    flat=True,
                )
            )
        else:
            custom_package = attempt.custom_package
            booking = Booking.objects.create(
                user=attempt.user,
                item_type=Booking.ItemType.CUSTOM_PACKAGE,
                custom_package=custom_package,
                booking_date=attempt.booking_date,
                booking_end_date=attempt.booking_end_date,
                guest_count=attempt.guest_count,
                customer_name=attempt.customer_name,
                customer_email=attempt.customer_email,
                customer_phone=attempt.customer_phone,
                total_price=attempt.total_price,
                item_title=(
                    custom_package.package_title
                    or "My package"
                ),
                customer_notes=attempt.customer_notes,
            )
            booking.package_services.set(
                custom_package.package_services.values_list(
                    "service_id",
                    flat=True,
                )
            )
        try:
            attach_reservations_to_booking(attempt.receipt, booking)
        except BookingUnavailableError:
            item = attempt.package or attempt.custom_package
            item_type = (
                "CATALOG_PACKAGE"
                if attempt.package_id
                else "CUSTOM_PACKAGE"
            )
            reserve_booking_dates(
                seller_ids_for_item(item_type, item),
                attempt.booking_date,
                attempt.booking_end_date or attempt.booking_date,
                booking=booking,
            )
        ensure_booking_seller_decisions(booking)
        create_booking_earnings(booking)
        attempt.booking = booking
        attempt.payment_id = payment_id
        attempt.status = PackagePaymentAttempt.Status.PAID
        attempt.save(update_fields=["booking", "payment_id", "status"])
        transaction.on_commit(
            lambda booking_id=booking.pk: send_booking_confirmation_email(
                booking_id
            )
        )
        return booking


def send_booking_confirmation_email(booking_id):
    booking = Booking.objects.select_related("user").get(pk=booking_id)
    send_booking_email(
        booking,
        subject=f"Booking request received: {booking.item_title}",
        message=(
            f"Hello {booking.customer_name or booking.user.get_full_name() or booking.user.username},\n\n"
            f"Your payment was received for booking #{booking.pk}.\n"
            f"Package/event: {booking.item_title}\n"
            f"Date: {booking.booking_date:%d %b %Y}"
            + (
                f" to {booking.booking_end_date:%d %b %Y}"
                if booking.booking_end_date
                and booking.booking_end_date != booking.booking_date
                else ""
            )
            + f"\nAmount paid: INR {booking.total_price:.2f}\n"
            "The seller will respond to your booking request shortly."
        ),
    )


def refund_captured_payment_for_unavailable_date(attempt_id, payment_id):
    attempt = PackagePaymentAttempt.objects.get(pk=attempt_id)
    try:
        refund = razorpay_client().payment.refund(
            payment_id,
            {
                "amount": attempt.amount_paise,
                "notes": {
                    "payment_attempt_id": str(attempt.pk),
                    "reason": "The selected booking date became unavailable.",
                },
            },
        )
    except (*RAZORPAY_API_ERRORS, KeyError, TypeError):
        logger.exception(
            "Unable to refund captured payment for unavailable booking date, attempt %s.",
            attempt.pk,
        )
        with transaction.atomic():
            attempt = PackagePaymentAttempt.objects.select_for_update().get(
                pk=attempt.pk
            )
            attempt.status = PackagePaymentAttempt.Status.FAILED
            attempt.save(update_fields=["status"])
            BookingDateReservation.objects.filter(
                payment_receipt=attempt.receipt
            ).delete()
        return None

    with transaction.atomic():
        attempt = PackagePaymentAttempt.objects.select_for_update().get(
            pk=attempt.pk
        )
        attempt.status = PackagePaymentAttempt.Status.FAILED
        attempt.save(update_fields=["status"])
        BookingDateReservation.objects.filter(
            payment_receipt=attempt.receipt
        ).delete()
    return refund.get("id")


@login_required(login_url="/accounts/login/")
def package_booking_page(request, package_id):
    if not is_regular_user(request.user):
        messages.error(
            request,
            "This section is available to customer accounts only.",
        )
        return redirect("home")

    package = get_object_or_404(
        CatalogPackage.objects
        .filter(is_deleted=False)
        .exclude(event__is_deleted=True)
        .exclude(package_items__service__is_deleted=True)
        .select_related("event", "seller", "seller__user")
        .prefetch_related("package_items__service"),
        pk=package_id,
    )
    initial = {}
    if request.method == "GET":
        requested_date = request.GET.get("booking_date", "").strip()
        try:
            chosen_date = date.fromisoformat(requested_date) if requested_date else None
            if chosen_date and chosen_date >= timezone.localdate():
                initial["booking_date"] = chosen_date
                initial["booking_end_date"] = chosen_date
        except (TypeError, ValueError):
            pass

    form = PackageBookingForm(
        request.POST if request.method == "POST" else None,
        package=package,
        user=request.user,
        initial=initial,
    )
    payment_options = None

    if request.method == "POST" and form.is_valid():
        guest_count = form.cleaned_data["guest_count"]
        total_price = package.total_price + PACKAGE_GUEST_PRICE * guest_count
        if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
            messages.error(
                request,
                "Online payment is not configured yet. Please contact support.",
            )
        else:
            try:
                with transaction.atomic():
                    locked_package = CatalogPackage.objects.select_for_update().get(
                        pk=package.pk
                    )
                    attempt = PackagePaymentAttempt.objects.create(
                        user=request.user,
                        package=locked_package,
                        receipt=f"pkg-{uuid.uuid4().hex}",
                        amount_paise=int(total_price * 100),
                        total_price=total_price,
                        booking_date=form.cleaned_data["booking_date"],
                        booking_end_date=form.cleaned_data["booking_end_date"],
                        guest_count=guest_count,
                        customer_name=form.cleaned_data["customer_name"].strip(),
                        customer_email=form.cleaned_data["customer_email"].strip(),
                        customer_phone=form.cleaned_data["customer_phone"].strip(),
                        customer_notes=form.cleaned_data["customer_notes"],
                    )
                    reserve_booking_dates(
                        seller_ids_for_item("CATALOG_PACKAGE", locked_package),
                        attempt.booking_date,
                        attempt.booking_end_date or attempt.booking_date,
                        payment_receipt=attempt.receipt,
                    )
            except BookingUnavailableError as error:
                form.add_error("booking_date", str(error))
            else:
                try:
                    order = razorpay_client().order.create(
                        data={
                            "amount": attempt.amount_paise,
                            "currency": "INR",
                            "receipt": attempt.receipt,
                            "notes": {
                                "customer_id": str(request.user.pk),
                                "package_id": str(package.pk),
                            },
                        }
                    )
                    attempt.order_id = order["id"]
                    attempt.save(update_fields=["order_id"])
                except (*RAZORPAY_API_ERRORS, KeyError, TypeError):
                    attempt.status = PackagePaymentAttempt.Status.FAILED
                    attempt.save(update_fields=["status"])
                    BookingDateReservation.objects.filter(
                        payment_receipt=attempt.receipt
                    ).delete()
                    logger.exception(
                        "Unable to create Razorpay order for payment attempt %s",
                        attempt.pk,
                    )
                    messages.error(
                        request,
                        "We could not start payment. Please try again.",
                    )
                else:
                    payment_options = {
                        "key": settings.RAZORPAY_KEY_ID,
                        "order_id": attempt.order_id,
                        "amount": attempt.amount_paise,
                        "currency": "INR",
                        "attempt_id": attempt.pk,
                        "name": "EventSphere",
                        "description": f"Full payment for {package.title}",
                        "prefill": {
                            "name": attempt.customer_name,
                            "email": attempt.customer_email,
                            "contact": attempt.customer_phone,
                        },
                        "config": {
                            "display": {
                                "blocks": {
                                    "upi": {
                                        "name": "Pay with UPI",
                                        "instruments": [{"method": "upi"}],
                                    },
                                },
                                "sequence": ["block.upi"],
                                "preferences": {
                                    "show_default_blocks": True,
                                },
                            },
                        },
                        "verify_url": reverse("verify-package-payment"),
                    }

    return render(
        request,
        "payments/package_booking.html",
        package_booking_context(package, form, payment_options),
    )


@login_required(login_url="/accounts/login/")
def custom_package_booking_page(request, package_id):
    if not is_regular_user(request.user):
        messages.error(request, "This section is available to customer accounts only.")
        return redirect("home")

    package = get_object_or_404(
        EventPackage.objects
        .select_related("event")
        .prefetch_related("package_services__service__seller"),
        pk=package_id,
        user=request.user,
    )
    form = PackageBookingForm(
        request.POST if request.method == "POST" else None,
        package=package,
        user=request.user,
        include_guest_count=False,
        initial={"booking_date": package.event_date},
    )
    payment_options = None

    if request.method == "POST" and form.is_valid():
        if package.total_cost <= 0:
            messages.error(
                request,
                "This custom package needs a positive total before it can be paid.",
            )
        elif not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
            messages.error(
                request,
                "Online payment is not configured yet. Please contact support.",
            )
        else:
            guest_count = package.guest_count
            total_price = (
                package.total_cost + PACKAGE_GUEST_PRICE * guest_count
            )
            try:
                with transaction.atomic():
                    locked_package = EventPackage.objects.select_for_update().get(
                        pk=package.pk
                    )
                    attempt = PackagePaymentAttempt.objects.create(
                        user=request.user,
                        custom_package=locked_package,
                        receipt=f"custom-{uuid.uuid4().hex}",
                        amount_paise=int(total_price * 100),
                        total_price=total_price,
                        booking_date=form.cleaned_data["booking_date"],
                        booking_end_date=form.cleaned_data["booking_end_date"],
                        guest_count=guest_count,
                        customer_name=form.cleaned_data["customer_name"].strip(),
                        customer_email=form.cleaned_data["customer_email"].strip(),
                        customer_phone=form.cleaned_data["customer_phone"].strip(),
                        customer_notes=form.cleaned_data["customer_notes"],
                    )
                    reserve_booking_dates(
                        seller_ids_for_item("CUSTOM_PACKAGE", locked_package),
                        attempt.booking_date,
                        attempt.booking_end_date or attempt.booking_date,
                        payment_receipt=attempt.receipt,
                    )
            except BookingUnavailableError as error:
                form.add_error("booking_date", str(error))
            else:
                try:
                    order = razorpay_client().order.create(
                        data={
                            "amount": attempt.amount_paise,
                            "currency": "INR",
                            "receipt": attempt.receipt,
                            "notes": {
                                "customer_id": str(request.user.pk),
                                "custom_package_id": str(package.pk),
                            },
                        }
                    )
                    attempt.order_id = order["id"]
                    attempt.save(update_fields=["order_id"])
                except (*RAZORPAY_API_ERRORS, KeyError, TypeError):
                    attempt.status = PackagePaymentAttempt.Status.FAILED
                    attempt.save(update_fields=["status"])
                    BookingDateReservation.objects.filter(
                        payment_receipt=attempt.receipt
                    ).delete()
                    logger.exception(
                        "Unable to create Razorpay order for custom payment attempt %s",
                        attempt.pk,
                    )
                    messages.error(
                        request,
                        "We could not start payment. Please try again.",
                    )
                else:
                    payment_options = {
                        "key": settings.RAZORPAY_KEY_ID,
                        "order_id": attempt.order_id,
                        "amount": attempt.amount_paise,
                        "currency": "INR",
                        "attempt_id": attempt.pk,
                        "name": "EventSphere",
                        "description": package.package_title or "My package",
                        "prefill": {
                            "name": attempt.customer_name,
                            "email": attempt.customer_email,
                            "contact": attempt.customer_phone,
                        },
                        "verify_url": reverse("verify-package-payment"),
                    }

    guest_count = package.guest_count

    return render(
        request,
        "payments/custom_package_booking.html",
        {
            **package_booking_context(package, form, payment_options),
            "package": package,
            "guest_count": guest_count,
            "guest_total": PACKAGE_GUEST_PRICE * guest_count,
            "total_price": package.total_cost + PACKAGE_GUEST_PRICE * guest_count,
        },
    )


@login_required(login_url="/accounts/login/")
@require_POST
def verify_package_payment(request):
    if not is_regular_user(request.user):
        return JsonResponse({"error": "Customer account required."}, status=403)
    if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
        return JsonResponse({"error": "Payment is not configured."}, status=503)

    attempt = get_object_or_404(
        PackagePaymentAttempt,
        pk=request.POST.get("attempt_id"),
        user=request.user,
    )
    order_id = request.POST.get("razorpay_order_id", "")
    payment_id = request.POST.get("razorpay_payment_id", "")
    signature = request.POST.get("razorpay_signature", "")
    if not order_id or not payment_id or not signature or order_id != attempt.order_id:
        return JsonResponse({"error": "Invalid payment response."}, status=400)

    client = razorpay_client()
    try:
        client.utility.verify_payment_signature(
            {
                "razorpay_order_id": order_id,
                "razorpay_payment_id": payment_id,
                "razorpay_signature": signature,
            }
        )
        payment = client.payment.fetch(payment_id)
        if payment.get("status") == "authorized":
            payment = client.payment.capture(
                payment_id,
                attempt.amount_paise,
                {"currency": "INR"},
            )
    except razorpay.errors.SignatureVerificationError:
        return JsonResponse({"error": "Payment signature is invalid."}, status=400)
    except RAZORPAY_API_ERRORS:
        logger.exception(
            "Unable to verify Razorpay payment for attempt %s",
            attempt.pk,
        )
        return JsonResponse(
            {"error": "Payment verification is temporarily unavailable."},
            status=502,
        )

    try:
        booking = complete_package_payment(attempt.pk, payment)
    except BookingUnavailableError:
        refund_id = refund_captured_payment_for_unavailable_date(
            attempt.pk,
            payment_id,
        )
        if refund_id:
            return JsonResponse(
                {
                    "error": (
                        "That date is no longer available. A refund was initiated."
                    ),
                    "refund_id": refund_id,
                },
                status=409,
            )
        return JsonResponse(
            {
                "error": (
                    "The date became unavailable and the payment refund could not "
                    "be confirmed. Please contact support."
                )
            },
            status=502,
        )
    except (PackagePaymentAttempt.DoesNotExist, KeyError, TypeError, ValueError):
        logger.exception(
            "Razorpay payment did not match attempt %s",
            attempt.pk,
        )
        return JsonResponse(
            {"error": "Payment could not be verified for this booking."},
            status=400,
        )
    return JsonResponse(
        {"redirect_url": reverse("booking-detail", args=[booking.pk])}
    )


@csrf_exempt
@require_POST
def razorpay_webhook(request):
    webhook_secret = getattr(settings, "RAZORPAY_WEBHOOK_SECRET", "")
    signature = request.headers.get("X-Razorpay-Signature", "")
    if not webhook_secret or not signature:
        return JsonResponse({"error": "Webhook is not configured."}, status=503)

    expected_signature = hmac.new(
        webhook_secret.encode("utf-8"),
        request.body,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected_signature, signature):
        return JsonResponse({"error": "Invalid webhook signature."}, status=400)

    try:
        event = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid webhook payload."}, status=400)

    if event.get("event") != "payment.captured":
        return JsonResponse({"status": "ignored"})

    try:
        payment = event["payload"]["payment"]["entity"]
        attempt = PackagePaymentAttempt.objects.get(order_id=payment["order_id"])
        complete_package_payment(attempt.pk, payment)
    except BookingUnavailableError:
        refund_id = refund_captured_payment_for_unavailable_date(
            attempt.pk,
            payment["id"],
        )
        if not refund_id:
            return JsonResponse(
                {"error": "The captured payment refund could not be confirmed."},
                status=502,
            )
        return JsonResponse(
            {"status": "date_unavailable", "refund_id": refund_id},
            status=200,
        )
    except PackagePaymentAttempt.DoesNotExist:
        logger.error("Captured Razorpay payment has no matching order.")
        return JsonResponse({"error": "Order not found."}, status=404)
    except (KeyError, TypeError, ValueError):
        logger.exception("Unable to process captured Razorpay webhook.")
        return JsonResponse({"error": "Webhook payment data is invalid."}, status=400)
    return JsonResponse({"status": "processed"})


def is_seller(user):
    return (
        user.is_authenticated
        and not user.is_staff
        and getattr(getattr(user, "profile", None), "role", None) == "SELLER"
        and hasattr(user, "seller_profile")
    )


def seller_required(view):
    return login_required(login_url="/accounts/login/")(
        user_passes_test(is_seller, login_url="/accounts/login/")(view)
    )


admin_required = user_passes_test(
    lambda user: user.is_authenticated and user.is_staff,
    login_url="/accounts/login/",
)


@login_required(login_url="/accounts/login/")
@require_GET
def package_availability_api(request, package_id):
    if not is_regular_user(request.user):
        return JsonResponse({"error": "Customer account required."}, status=403)
    package = get_object_or_404(
        CatalogPackage.objects
        .filter(is_deleted=False, event__is_deleted=False)
        .exclude(package_items__service__is_deleted=True)
        .prefetch_related("package_items__service"),
        pk=package_id,
    )
    month_value = request.GET.get("month", "")
    try:
        year, month = (int(value) for value in month_value.split("-", 1))
        month_start = date(year, month, 1)
    except (ValueError, TypeError):
        return JsonResponse(
            {"error": "Use a valid month in YYYY-MM format."},
            status=400,
        )
    month_end = date(
        year,
        month,
        calendar.monthrange(year, month)[1],
    )
    seller_ids = seller_ids_for_item("CATALOG_PACKAGE", package)
    blocked_dates = unavailable_dates_for_sellers(
        seller_ids,
        month_start,
        month_end,
    )
    return JsonResponse(
        {
            "month": month_value,
            "unavailable_dates": [
                unavailable_date.isoformat()
                for unavailable_date in blocked_dates
            ],
        }
    )


@login_required(login_url="/accounts/login/")
@require_GET
def custom_package_availability_api(request, package_id):
    if not is_regular_user(request.user):
        return JsonResponse({"error": "Customer account required."}, status=403)
    package = get_object_or_404(
        EventPackage.objects
        .select_related("event")
        .prefetch_related("package_services__service"),
        pk=package_id,
        user=request.user,
    )
    month_value = request.GET.get("month", "")
    try:
        year, month = (int(value) for value in month_value.split("-", 1))
        month_start = date(year, month, 1)
        month_end = date(
            year,
            month,
            calendar.monthrange(year, month)[1],
        )
    except (ValueError, TypeError):
        return JsonResponse(
            {"error": "Use a valid month in YYYY-MM format."},
            status=400,
        )
    blocked_dates = unavailable_dates_for_sellers(
        seller_ids_for_item("CUSTOM_PACKAGE", package),
        month_start,
        month_end,
    )
    return JsonResponse(
        {
            "month": month_value,
            "unavailable_dates": [
                unavailable_date.isoformat()
                for unavailable_date in blocked_dates
            ],
        }
    )


def get_seller_bookings(seller):
    bookings = (
        Booking.objects
        .filter(
            Q(seller=seller)
            | Q(package_event__seller=seller)
            | Q(custom_package__package_services__seller=seller)
            | Q(custom_package__package_services__service__seller=seller)
            | Q(package_services__seller=seller)
        )
        .select_related(
            "user",
            "event",
            "service",
            "catalog_package",
            "package_event",
            "seller",
            "custom_package",
            "custom_package__event",
        )
        .prefetch_related(
            "package_services",
            "custom_package__package_services__service__seller",
            "custom_package__package_services__seller",
            "seller_decisions",
            "seller_decisions__seller",
        )
        .distinct()
        .order_by("-created_at")
    )
    for booking in bookings:
        if not booking.seller_decisions.exists():
            ensure_booking_seller_decisions(booking)
            if booking.status == Booking.Status.CONFIRMED:
                BookingSellerDecision.objects.filter(
                    booking=booking,
                    seller=seller,
                ).update(status=BookingSellerDecision.Status.ACCEPTED)
    return bookings


@seller_required
def seller_bookings_page(request):
    seller = request.user.seller_profile
    bookings = get_seller_bookings(seller)
    today = timezone.localdate()
    decisions = list(
        BookingSellerDecision.objects.filter(
            booking__in=bookings,
            seller=seller,
        ).select_related("booking", "booking__user")
    )
    for decision in decisions:
        event_end_date = (
            decision.booking.booking_end_date or decision.booking.booking_date
        )
        decision.event_has_ended = event_end_date < today
        decision.is_completion_complete = (
            decision.booking.status == Booking.Status.COMPLETED
            and decision.booking.admin_completed_at is not None
        )
    return render(
        request,
        "payments/seller_bookings.html",
        {"decisions": decisions},
    )


@seller_required
def seller_availability_page(request):
    seller = request.user.seller_profile
    if request.method == "POST":
        action = request.POST.get("action")
        unavailable_date = parse_date(request.POST.get("date", ""))
        if not unavailable_date or unavailable_date < timezone.localdate():
            messages.error(request, "Choose today or a future date.")
        elif action == "block":
            with transaction.atomic():
                Seller.objects.select_for_update().get(pk=seller.pk)
                has_booking = BookingDateReservation.objects.filter(
                    seller=seller,
                    date=unavailable_date,
                    booking__isnull=False,
                ).exists()
                has_payment_hold = BookingDateReservation.objects.filter(
                    seller=seller,
                    date=unavailable_date,
                    booking__isnull=True,
                    hold_expires_at__gt=timezone.now(),
                ).exists()
                if has_booking or has_payment_hold:
                    messages.error(
                        request,
                        "This date already has a booking or an active checkout hold.",
                    )
                else:
                    SellerUnavailableDate.objects.get_or_create(
                        seller=seller,
                        date=unavailable_date,
                    )
                    messages.success(request, "The date is now marked unavailable.")
        elif action == "unblock":
            with transaction.atomic():
                Seller.objects.select_for_update().get(pk=seller.pk)
                SellerUnavailableDate.objects.filter(
                    seller=seller,
                    date=unavailable_date,
                ).delete()
            messages.success(request, "The date is available again.")
        else:
            messages.error(request, "Choose a valid availability action.")
        return redirect("seller-availability")

    unavailable_dates = SellerUnavailableDate.objects.filter(
        seller=seller,
        date__gte=timezone.localdate(),
    )
    reserved_dates = (
        BookingDateReservation.objects.filter(
            seller=seller,
            date__gte=timezone.localdate(),
        )
        .filter(
            Q(booking__isnull=False)
            | Q(hold_expires_at__gt=timezone.now())
        )
        .order_by("date")
    )
    return render(
        request,
        "payments/seller_availability.html",
        {
            "unavailable_dates": unavailable_dates,
            "reserved_dates": reserved_dates,
            "today": timezone.localdate(),
        },
    )


@seller_required
@require_POST
def seller_booking_decision(request, booking_id):
    seller = request.user.seller_profile
    booking = get_object_or_404(get_seller_bookings(seller), pk=booking_id)
    ensure_booking_seller_decisions(booking)
    action = request.POST.get("action")
    reason = request.POST.get("rejection_reason", "").strip()
    if action == "reject" and not reason:
        messages.error(request, "Enter a reason before rejecting the booking.")
        return redirect("seller-bookings")
    if action not in {"accept", "reject"}:
        messages.error(request, "Select a valid booking action.")
        return redirect("seller-bookings")

    with transaction.atomic():
        booking = Booking.objects.select_for_update().get(pk=booking.pk)
        decision = get_object_or_404(
            BookingSellerDecision.objects.select_for_update(),
            booking=booking,
            seller=seller,
        )
        if booking.status in (
            Booking.Status.CANCELLED,
            Booking.Status.COMPLETED,
            Booking.Status.REJECTED,
        ) or decision.status != BookingSellerDecision.Status.PENDING:
            messages.error(request, "This booking can no longer be changed.")
            return redirect("seller-bookings")
        decision.status = (
            BookingSellerDecision.Status.ACCEPTED
            if action == "accept"
            else BookingSellerDecision.Status.REJECTED
        )
        decision.rejection_reason = reason if action == "reject" else ""
        decision.save(update_fields=["status", "rejection_reason", "updated_at"])
        all_decisions = list(
            booking.seller_decisions.select_related("seller").all()
        )
        rejected = [item for item in all_decisions if item.status == "REJECTED"]
        if rejected:
            booking.status = Booking.Status.REJECTED
            booking.rejection_reason = "; ".join(
                f"{item.seller.business_name}: {item.rejection_reason}"
                for item in rejected
            )
        elif all(item.status == "ACCEPTED" for item in all_decisions):
            booking.status = Booking.Status.CONFIRMED
            booking.rejection_reason = ""
        else:
            booking.status = Booking.Status.PENDING
            booking.rejection_reason = ""
        booking.save(
            update_fields=["status", "rejection_reason", "updated_at"]
        )
        if booking.status == Booking.Status.REJECTED:
            payment_attempt = getattr(booking, "payment_attempt", None)
            if (
                payment_attempt
                and payment_attempt.status == PackagePaymentAttempt.Status.PAID
                and not booking.cancellation_requests.filter(
                    status__in=[
                        BookingCancellationRequest.Status.REQUESTED,
                        BookingCancellationRequest.Status.PROCESSING,
                        BookingCancellationRequest.Status.FAILED,
                    ]
                ).exists()
            ):
                BookingCancellationRequest.objects.create(
                    booking=booking,
                    requested_by=booking.user,
                    reason="A seller declined this booking. Please review the full refund.",
                    refund_amount=payment_attempt.total_price,
                )
            else:
                release_booking_reservations(booking)
            transaction.on_commit(
                lambda booking_id=booking.pk: send_booking_email(
                    Booking.objects.select_related("user").get(pk=booking_id),
                    "Booking request declined",
                    f"Your booking request #{booking.pk} for {booking.item_title} "
                    "was declined. Please contact support if you need help.",
                )
            )
        elif booking.status == Booking.Status.CONFIRMED:
            transaction.on_commit(
                lambda booking_id=booking.pk: send_booking_email(
                    Booking.objects.select_related("user").get(pk=booking_id),
                    "Your booking is confirmed",
                    f"Your booking #{booking.pk} for {booking.item_title} has "
                    "been accepted by all sellers.",
                )
            )

    messages.success(
        request,
        "Booking response saved." if action == "accept"
        else "Booking rejected and the reason was recorded.",
    )
    return redirect("seller-bookings")


@seller_required
@require_POST
def seller_report_booking_completion(request, booking_id):
    seller = request.user.seller_profile
    with transaction.atomic():
        booking = get_object_or_404(
            Booking.objects.select_for_update(),
            pk=booking_id,
            status=Booking.Status.CONFIRMED,
        )
        event_end_date = booking.booking_end_date or booking.booking_date
        if event_end_date >= timezone.localdate():
            messages.error(
                request,
                "You can report completion after the event has ended.",
            )
            return redirect("seller-bookings")

        decision = get_object_or_404(
            BookingSellerDecision.objects.select_for_update(),
            booking=booking,
            seller=seller,
            status=BookingSellerDecision.Status.ACCEPTED,
        )
        if decision.seller_completed_at:
            messages.info(
                request,
                "You have already reported this event as complete.",
            )
        else:
            decision.seller_completed_at = timezone.now()
            decision.save(
                update_fields=["seller_completed_at", "updated_at"]
            )
            messages.success(
                request,
                "Completion reported. The customer can confirm delivery, then admin will review it.",
            )
    return redirect("seller-bookings")


@seller_required
def seller_payments_page(request):
    seller = request.user.seller_profile
    today = timezone.localdate()
    earnings = SellerEarning.objects.filter(seller=seller)
    available_earnings = earnings.filter(
        available_on__lte=today,
        payout_request__isnull=True,
        booking__status=Booking.Status.COMPLETED,
        booking__admin_completed_at__isnull=False,
    )
    transactions = (
        earnings.select_related(
            "booking",
            "booking__user",
            "booking__payment_attempt",
            "payout_request",
        )
        .order_by("-booking__created_at")[:100]
    )
    awaiting_confirmation = earnings.filter(
        booking__status=Booking.Status.CONFIRMED,
        available_on__lte=today,
        payout_request__isnull=True,
        booking__admin_completed_at__isnull=True,
    ).aggregate(total=Sum("seller_amount"))["total"] or Decimal("0.00")
    if request.method == "POST":
        with transaction.atomic():
            eligible = list(
                available_earnings.select_for_update().order_by("pk")
            )
            total = sum(
                (earning.seller_amount for earning in eligible),
                Decimal("0.00"),
            )
            if total <= 0 or not eligible:
                messages.error(
                    request,
                    "There are no event-date-eligible earnings to request.",
                )
            else:
                payout = PayoutRequest.objects.create(
                    seller=seller,
                    amount=total,
                )
                SellerEarning.objects.filter(
                    pk__in=[earning.pk for earning in eligible],
                    payout_request__isnull=True,
                ).update(payout_request=payout)
                messages.success(
                    request,
                    "Your payout request was sent to the admin.",
                )
        return redirect("seller-payments")

    context = {
        "earned_total": earnings.aggregate(total=Sum("seller_amount"))["total"] or Decimal("0.00"),
        "available_total": available_earnings.aggregate(total=Sum("seller_amount"))["total"] or Decimal("0.00"),
        "requested_total": earnings.filter(
            payout_request__status=PayoutRequest.Status.REQUESTED
        ).aggregate(total=Sum("seller_amount"))["total"] or Decimal("0.00"),
        "paid_total": earnings.filter(
            payout_request__status=PayoutRequest.Status.PAID
        ).aggregate(total=Sum("seller_amount"))["total"] or Decimal("0.00"),
        "payout_requests": PayoutRequest.objects.filter(
            seller=seller
        ).order_by("-created_at"),
        "transactions": transactions,
        "awaiting_confirmation": awaiting_confirmation,
        "monthly_earnings": monthly_amounts(earnings, "seller_amount"),
    }
    return render(request, "payments/seller_payments.html", context)


@admin_required
def admin_bookings_page(request):
    bookings = (
        Booking.objects
        .select_related(
            "user",
            "event",
            "service",
            "catalog_package",
            "package_event",
            "seller",
            "custom_package",
            "payment_attempt",
            "custom_package__event__seller",
        )
        .prefetch_related(
            "package_services",
            "custom_package__package_services__service__seller",
            "seller_decisions__seller",
            "seller_earnings__seller",
        )
        .order_by("-created_at")
    )
    bookings = list(bookings)
    for booking in bookings:
        decisions = list(booking.seller_decisions.all())
        booking.can_admin_complete = (
            booking.status == Booking.Status.CONFIRMED
            and booking.customer_confirmed_at is not None
            and booking.admin_completed_at is None
            and bool(decisions)
            and all(
                decision.status == BookingSellerDecision.Status.ACCEPTED
                and decision.seller_completed_at is not None
                for decision in decisions
            )
        )
    ready_for_admin_count = sum(
        booking.can_admin_complete for booking in bookings
    )
    completed_count = sum(
        booking.admin_completed_at is not None for booking in bookings
    )
    return render(
        request,
        "payments/admin_bookings.html",
        {
            "bookings": bookings,
            "ready_for_admin_count": ready_for_admin_count,
            "completed_count": completed_count,
            "cancellation_requests": BookingCancellationRequest.objects
            .filter(
                status__in=[
                    BookingCancellationRequest.Status.REQUESTED,
                    BookingCancellationRequest.Status.FAILED,
                ]
            )
            .select_related("booking", "requested_by")
            .order_by("requested_at"),
        },
    )


@admin_required
@require_POST
def admin_process_cancellation(request, request_id):
    action = request.POST.get("action")
    admin_note = request.POST.get("admin_note", "").strip()
    if action not in {"approve", "reject"}:
        messages.error(request, "Choose whether to approve or reject the request.")
        return redirect("admin-bookings")
    if action == "reject" and not admin_note:
        messages.error(request, "Add a reason before rejecting the cancellation.")
        return redirect("admin-bookings")

    with transaction.atomic():
        cancellation = get_object_or_404(
            BookingCancellationRequest.objects.select_for_update(),
            pk=request_id,
        )
        if cancellation.status not in (
            BookingCancellationRequest.Status.REQUESTED,
            BookingCancellationRequest.Status.FAILED,
        ):
            messages.error(request, "This cancellation request was already processed.")
            return redirect("admin-bookings")
        booking = Booking.objects.select_for_update().get(
            pk=cancellation.booking_id
        )
        if action == "reject":
            cancellation.status = BookingCancellationRequest.Status.REJECTED
            cancellation.admin_note = admin_note
            cancellation.processed_at = timezone.now()
            cancellation.save(
                update_fields=[
                    "status",
                    "admin_note",
                    "processed_at",
                ]
            )
            transaction.on_commit(
                lambda booking_id=booking.pk, note=admin_note: send_booking_email(
                    Booking.objects.select_related("user").get(pk=booking_id),
                    "Cancellation request update",
                    f"Your cancellation request for booking #{booking.pk} was not approved.\n\n"
                    f"Admin note: {note}",
                )
            )
            messages.success(request, "Cancellation request rejected.")
            return redirect("admin-bookings")

        if booking.status not in (
            Booking.Status.PENDING,
            Booking.Status.CONFIRMED,
            Booking.Status.REJECTED,
        ):
            messages.error(request, "This booking can no longer be cancelled.")
            return redirect("admin-bookings")
        payment_attempt = getattr(booking, "payment_attempt", None)
        if cancellation.refund_amount > 0 and (
            not payment_attempt
            or payment_attempt.status != PackagePaymentAttempt.Status.PAID
            or not payment_attempt.payment_id
        ):
            messages.error(
                request,
                "A verified Razorpay payment is required before a refund can be processed.",
            )
            return redirect("admin-bookings")
        cancellation.status = BookingCancellationRequest.Status.PROCESSING
        cancellation.admin_note = admin_note
        cancellation.save(update_fields=["status", "admin_note"])

    refund_id = ""
    try:
        if cancellation.refund_amount > 0:
            refund = razorpay_client().payment.refund(
                payment_attempt.payment_id,
                {
                    "amount": int(cancellation.refund_amount * 100),
                    "notes": {
                        "booking_id": str(booking.pk),
                        "cancellation_request_id": str(cancellation.pk),
                    },
                },
            )
            refund_id = refund["id"]
    except (*RAZORPAY_API_ERRORS, KeyError, TypeError):
        logger.exception(
            "Unable to process refund for cancellation request %s.",
            cancellation.pk,
        )
        cancellation.status = BookingCancellationRequest.Status.FAILED
        cancellation.admin_note = (
            "Razorpay could not confirm the refund. Review the gateway before retrying."
        )
        cancellation.save(
            update_fields=["status", "admin_note"],
        )
        messages.error(request, "Refund failed. Review the gateway before retrying.")
        return redirect("admin-bookings")

    with transaction.atomic():
        cancellation = BookingCancellationRequest.objects.select_for_update().get(
            pk=cancellation.pk
        )
        booking = Booking.objects.select_for_update().get(pk=booking.pk)
        cancellation.status = BookingCancellationRequest.Status.REFUNDED
        cancellation.refund_id = refund_id
        cancellation.processed_at = timezone.now()
        cancellation.save(
            update_fields=["status", "refund_id", "processed_at"]
        )
        booking.status = Booking.Status.CANCELLED
        booking.cancelled_at = timezone.now()
        booking.save(update_fields=["status", "cancelled_at", "updated_at"])
        release_booking_reservations(booking)
        transaction.on_commit(
            lambda booking_id=booking.pk, amount=cancellation.refund_amount: send_booking_email(
                Booking.objects.select_related("user").get(pk=booking_id),
                "Booking cancelled and refund processed",
                f"Booking #{booking.pk} has been cancelled. "
                f"Refund amount: INR {amount:.2f}."
                + (f"\nRazorpay refund reference: {refund_id}" if refund_id else ""),
            )
        )

    messages.success(request, "Booking cancelled and refund processing was confirmed.")
    return redirect("admin-bookings")


@admin_required
@require_POST
def admin_complete_booking(request, booking_id):
    with transaction.atomic():
        booking = get_object_or_404(
            Booking.objects.select_for_update(),
            pk=booking_id,
            status=Booking.Status.CONFIRMED,
        )
        if booking.customer_confirmed_at is None:
            messages.error(
                request,
                "The customer must confirm completion before admin approval.",
            )
            return redirect("admin-bookings")
        if booking.admin_completed_at is not None:
            messages.info(request, "This booking is already admin-approved.")
            return redirect("admin-bookings")

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
                "Every accepted seller must report completion before admin approval.",
            )
            return redirect("admin-bookings")

        booking.status = Booking.Status.COMPLETED
        booking.admin_completed_at = timezone.now()
        booking.save(
            update_fields=["status", "admin_completed_at", "updated_at"]
        )

    messages.success(
        request,
        "Booking marked complete. Seller earnings are now eligible according to the payout schedule.",
    )
    return redirect("admin-bookings")


@admin_required
def admin_payments_page(request):
    if request.method == "POST":
        with transaction.atomic():
            payout = get_object_or_404(
                PayoutRequest.objects.select_for_update(),
                pk=request.POST.get("payout_id"),
            )
            action = request.POST.get("action")
            note = request.POST.get("admin_note", "").strip()
            if payout.status != PayoutRequest.Status.REQUESTED:
                messages.error(
                    request,
                    "This payout request has already been processed.",
                )
            elif action == "paid":
                method = request.POST.get("payment_method", "").strip()
                reference = request.POST.get("payment_reference", "").strip()
                unapproved_earnings = payout.earnings.exclude(
                    booking__status=Booking.Status.COMPLETED,
                    booking__admin_completed_at__isnull=False,
                )
                if unapproved_earnings.exists():
                    messages.error(
                        request,
                        "This payout includes bookings that admin has not approved as complete.",
                    )
                elif not method or not reference:
                    messages.error(
                        request,
                        "Enter the payment method and transfer reference.",
                    )
                else:
                    payout.status = PayoutRequest.Status.PAID
                    payout.payment_method = method
                    payout.payment_reference = reference
                    payout.admin_note = note
                    payout.processed_at = timezone.now()
                    payout.save()
                    messages.success(request, "Payout marked as paid.")
            elif action == "reject":
                if not note:
                    messages.error(request, "Enter a reason for rejecting the payout.")
                else:
                    payout.status = PayoutRequest.Status.REJECTED
                    payout.admin_note = note
                    payout.processed_at = timezone.now()
                    payout.save()
                    SellerEarning.objects.filter(
                        payout_request=payout
                    ).update(payout_request=None)
                    messages.success(
                        request,
                        "Payout request rejected and earnings released.",
                    )
            else:
                messages.error(request, "Select a valid payout action.")
        return redirect("admin-payments")

    payout_requests = (
        PayoutRequest.objects
        .select_related("seller", "seller__user")
        .prefetch_related("earnings__booking")
        .order_by("status", "-created_at")
    )
    earnings = SellerEarning.objects.all()
    gross_earnings = earnings.annotate(
        gross_amount=F("seller_amount") + F("commission_amount")
    )
    payment_attempts = (
        PackagePaymentAttempt.objects
        .select_related("user", "package", "custom_package", "booking")
        .order_by("-created_at")[:100]
    )
    context = {
        "payout_requests": payout_requests,
        "payment_attempts": payment_attempts,
        "gross_payment_total": gross_earnings.aggregate(
            total=Sum("gross_amount")
        )["total"] or Decimal("0.00"),
        "commission_total": earnings.aggregate(total=Sum("commission_amount"))["total"] or Decimal("0.00"),
        "seller_paid_total": earnings.filter(
            payout_request__status=PayoutRequest.Status.PAID
        ).aggregate(total=Sum("seller_amount"))["total"] or Decimal("0.00"),
        "monthly_commissions": monthly_amounts(
            earnings,
            "commission_amount",
        ),
        "monthly_gross_payments": monthly_amounts(
            gross_earnings,
            "gross_amount",
        ),
    }
    return render(request, "payments/admin_payments.html", context)

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test

from dashboard.models import Seller, Event, Service
from bookings.models import Booking, BookingSellerDecision
from dashboard.analytics import monthly_counts, monthly_amounts
from packages.models import CatalogPackage, ServiceQuote
from django.shortcuts import get_object_or_404
from django.contrib import messages
from django.utils import timezone

from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Prefetch, Q, Sum

from packages.models import  CatalogPackageItem
from .forms import SellerCatalogPackageForm
from payments.models import SellerEarning



def is_seller(user):
    return (
        user.is_authenticated
        and not user.is_staff
        and hasattr(user, "profile")
        and user.profile.role == "SELLER"
    )


@login_required(login_url="/accounts/login/")
@user_passes_test(is_seller, login_url="/accounts/login/")
def seller_dashboard(request):
    seller = Seller.objects.filter(user=request.user).first()

    events = Event.objects.filter(
        seller__isnull=True,
        is_deleted=False,
    )
    services = Service.objects.filter(
        seller__isnull=True,
        is_deleted=False,
    )
    packages = CatalogPackage.objects.none()
    recent_packages = packages
    bookings = Booking.objects.none()
    recent_bookings = bookings
    custom_package_requests = BookingSellerDecision.objects.none()
    service_quote_requests = ServiceQuote.objects.none()

    if seller:
        service_quote_requests = (
            ServiceQuote.objects.filter(
                seller=seller,
                status=ServiceQuote.Status.PENDING,
            )
            .select_related("request", "request__customer")
            .order_by("-request__created_at")
        )
        packages = CatalogPackage.objects.filter(
            seller=seller,
            is_deleted=False,
        ).select_related(
            "event",
        ).prefetch_related(
            "package_items__service",
        ).order_by("-created_at")
        recent_packages = packages[:5]
        bookings = (
            Booking.objects.filter(
                Q(seller=seller)
                | Q(package_event__seller=seller)
                | Q(custom_package__package_services__seller=seller)
                | Q(custom_package__package_services__service__seller=seller)
                | Q(package_services__seller=seller)
            )
            .select_related("user", "catalog_package")
            .distinct()
            .order_by("-created_at")
        )
        custom_package_requests = (
            BookingSellerDecision.objects
            .filter(
                seller=seller,
                status=BookingSellerDecision.Status.PENDING,
                booking__item_type=Booking.ItemType.CUSTOM_PACKAGE,
                booking__status=Booking.Status.PENDING,
            )
            .select_related(
                "booking",
                "booking__user",
                "booking__package_event",
                "booking__custom_package",
            )
            .prefetch_related(
                "booking__custom_package__package_services__service__seller"
            )
            .order_by("-booking__created_at")[:5]
        )
        recent_bookings = list(
            bookings
            .select_related("user", "catalog_package", "payment_attempt")
            .prefetch_related(
                Prefetch(
                    "seller_decisions",
                    queryset=BookingSellerDecision.objects.filter(seller=seller),
                    to_attr="seller_dashboard_decisions",
                )
            )
            .order_by("-created_at")[:6]
        )
        today = timezone.localdate()
        for booking in recent_bookings:
            event_end_date = booking.booking_end_date or booking.booking_date
            own_decisions = booking.seller_dashboard_decisions
            if booking.admin_completed_at:
                booking.seller_completion_label = "Complete"
                booking.seller_completion_state = "complete"
            elif booking.status != Booking.Status.CONFIRMED:
                booking.seller_completion_label = booking.get_status_display()
                booking.seller_completion_state = "pending"
            elif booking.customer_confirmed_at:
                booking.seller_completion_label = "Awaiting admin approval"
                booking.seller_completion_state = "review"
            elif any(decision.seller_completed_at for decision in own_decisions):
                booking.seller_completion_label = "Awaiting customer confirmation"
                booking.seller_completion_state = "review"
            elif event_end_date < today:
                booking.seller_completion_label = "Pending · mark complete"
                booking.seller_completion_state = "pending"
            else:
                booking.seller_completion_label = "Pending · event upcoming"
                booking.seller_completion_state = "pending"

    context = {
        "seller": seller,
        "events_count": events.count(),
        "services_count": services.count(),
        "packages_count": packages.count(),
        "recent_packages": recent_packages,
        "bookings_count": bookings.count(),
        "pending_bookings_count": bookings.filter(
            status=Booking.Status.PENDING
        ).count(),
        "recent_bookings": recent_bookings,
        "custom_package_requests": custom_package_requests,
        "service_quote_requests": service_quote_requests,
        "monthly_bookings": monthly_counts(bookings),
        "earned_total": (
            SellerEarning.objects.filter(seller=seller)
            .aggregate(total=Sum("seller_amount"))["total"]
            if seller else 0
        ) or 0,
        "available_total": (
            SellerEarning.objects.filter(
                seller=seller,
                available_on__lte=timezone.localdate(),
                payout_request__isnull=True,
                booking__status=Booking.Status.COMPLETED,
                booking__admin_completed_at__isnull=False,
            ).aggregate(total=Sum("seller_amount"))["total"]
            if seller else 0
        ) or 0,
        "monthly_earnings": (
            monthly_amounts(
                SellerEarning.objects.filter(seller=seller),
                "seller_amount",
            )
            if seller else []
        ),
    }

    return render(
        request,
        "sellers/seller_dashboard.html",
        context
    )


@login_required(login_url="/accounts/login/")
@user_passes_test(is_seller, login_url="/accounts/login/")
def seller_service_quote_response(request, quote_id):
    if request.method != "POST":
        return redirect("seller-dashboard")

    seller = get_object_or_404(Seller, user=request.user)
    quote = get_object_or_404(ServiceQuote, pk=quote_id, seller=seller)
    if quote.status != ServiceQuote.Status.PENDING:
        messages.error(request, "This quote request has already been answered.")
        return redirect("seller-dashboard")

    action = request.POST.get("action", "")
    if action == "unavailable":
        quote.status = ServiceQuote.Status.UNAVAILABLE
        quote.message = request.POST.get("message", "").strip()[:2000]
        quote.responded_at = timezone.now()
        quote.save(update_fields=["status", "message", "responded_at"])
        messages.success(request, "You marked this service request as unavailable.")
        return redirect("seller-dashboard")

    if action != "quote":
        messages.error(request, "Choose whether to provide a quote or mark the request unavailable.")
        return redirect("seller-dashboard")

    try:
        quoted_price = Decimal(request.POST.get("quoted_price", "").strip())
    except (InvalidOperation, AttributeError):
        messages.error(request, "Enter a valid quote amount.")
        return redirect("seller-dashboard")
    if (
        not quoted_price.is_finite()
        or quoted_price <= 0
        or quoted_price > Decimal("99999999.99")
        or quoted_price.as_tuple().exponent < -2
    ):
        messages.error(
            request,
            "The quote must be greater than zero and have at most two decimal places.",
        )
        return redirect("seller-dashboard")

    quote.status = ServiceQuote.Status.QUOTED
    quote.quoted_price = quoted_price
    quote.message = request.POST.get("message", "").strip()[:2000]
    quote.responded_at = timezone.now()
    quote.save(
        update_fields=["status", "quoted_price", "message", "responded_at"]
    )
    messages.success(request, "Your quote has been sent to the customer.")
    return redirect("seller-dashboard")


@login_required(login_url="/accounts/login/")
@user_passes_test(is_seller, login_url="/accounts/login/")
def seller_events(request):
    seller = Seller.objects.filter(user=request.user).first()

    events = Event.objects.none()

    if seller:
        events = Event.objects.filter(
            seller=seller
        ).order_by("-created_at")

    context = {
        "events": events,
    }

    return render(
        request,
        "sellers/seller_events.html",
        context
    )



from django.shortcuts import render, redirect
from django.contrib import messages

from .forms import EventForm


@login_required(login_url="/accounts/login/")
@user_passes_test(is_seller, login_url="/accounts/login/")
def seller_create_event(request):
    seller = Seller.objects.filter(user=request.user).first()

    if seller is None:
        return render(
            request,
            "sellers/seller_create_event.html",
            {
                "form": EventForm(),
                "error": "Your seller profile was not found.",
            },
        )

    if request.method == "POST":
        form = EventForm(request.POST, request.FILES)

        if form.is_valid():
            event = form.save(commit=False)
            event.seller = seller
            event.save()

            messages.success(
                request,
                "Your event was created successfully!"
            )
            return redirect("seller-events")
    else:
        form = EventForm()

    return render(
        request,
        "sellers/seller_create_event.html",
        {"form": form},
    )



@login_required(login_url="/accounts/login/")
@user_passes_test(is_seller, login_url="/accounts/login/")
def seller_edit_event(request, event_id):
    seller = Seller.objects.filter(user=request.user).first()

    if seller is None:
        return redirect("seller-events")

    event = get_object_or_404(
        Event,
        id=event_id,
        seller=seller
    )

    if request.method == "POST":
        form = EventForm(
            request.POST,
            request.FILES,
            instance=event
        )

        if form.is_valid():
            form.save()
            messages.success(
                request,
                "Event updated successfully!"
            )
            return redirect("seller-events")
    else:
        form = EventForm(instance=event)

    return render(
        request,
        "sellers/seller_edit_event.html",
        {
            "form": form,
            "event": event,
        }
    )



@login_required(login_url="/accounts/login/")
@user_passes_test(is_seller, login_url="/accounts/login/")
def seller_view_event(request, event_id):
    seller = Seller.objects.filter(user=request.user).first()

    if seller is None:
        return redirect("seller-events")

    event = get_object_or_404(
        Event,
        id=event_id,
        seller=seller
    )

    return render(
        request,
        "sellers/seller_view_event.html",
        {"event": event}
    )

from django.db import transaction

@login_required
@user_passes_test(lambda u: hasattr(u, "seller_profile"))
def seller_delete_event(request, event_id):
    if request.method != "POST":
        return redirect("seller-events")

    seller = get_object_or_404(Seller, user=request.user)
    event = get_object_or_404(
        Event,
        id=event_id,
        seller=seller
    )

    image_name = event.image.name if event.image else None

    try:
        with transaction.atomic():
            event.delete()

        # Delete the image only after the database deletion succeeds.
        if image_name:
            event.image.storage.delete(image_name)

        messages.success(request, "Event deleted successfully!")

    except Exception:
        messages.error(
            request,
            "Event could not be deleted because related records may depend on it."
        )

    return redirect("seller-events")



from .forms import ServiceForm


@login_required(login_url="/accounts/login/")
@user_passes_test(is_seller, login_url="/accounts/login/")
def seller_services(request):
    seller = Seller.objects.filter(user=request.user).first()

    services = Service.objects.none()

    if seller:
        services = Service.objects.filter(
            seller=seller
        ).order_by("-created_at")

    return render(
        request,
        "sellers/seller_service.html",
        {"services": services},
    )


@login_required(login_url="/accounts/login/")
@user_passes_test(is_seller, login_url="/accounts/login/")
def seller_create_service(request):
    seller = Seller.objects.filter(user=request.user).first()

    if seller is None:
        messages.error(request, "Your seller profile was not found.")
        return redirect("seller-services")

    if request.method == "POST":
        form = ServiceForm(request.POST, request.FILES)

        if form.is_valid():
            service = form.save(commit=False)
            service.seller = seller
            service.save()

            messages.success(
                request,
                "Service created successfully!",
            )
            return redirect("seller-services")
    else:
        form = ServiceForm()

    return render(
        request,
        "sellers/seller_create_service.html",
        {"form": form},
    )


@login_required(login_url="/accounts/login/")
@user_passes_test(is_seller, login_url="/accounts/login/")
def seller_view_service(request, service_id):
    seller = Seller.objects.filter(user=request.user).first()

    if seller is None:
        return redirect("seller-services")

    service = get_object_or_404(
        Service,
        id=service_id,
        seller=seller,
    )

    return render(
        request,
        "sellers/seller_view_service.html",
        {"service": service},
    )


@login_required(login_url="/accounts/login/")
@user_passes_test(is_seller, login_url="/accounts/login/")
def seller_edit_service(request, service_id):
    seller = Seller.objects.filter(user=request.user).first()

    if seller is None:
        return redirect("seller-services")

    service = get_object_or_404(
        Service,
        id=service_id,
        seller=seller,
    )

    if request.method == "POST":
        form = ServiceForm(
            request.POST,
            request.FILES,
            instance=service,
        )

        if form.is_valid():
            form.save()

            messages.success(
                request,
                "Service updated successfully!",
            )
            return redirect("seller-services")
    else:
        form = ServiceForm(instance=service)

    return render(
        request,
        "sellers/seller_edit_service.html",
        {
            "form": form,
            "service": service,
        },
    )


@login_required(login_url="/accounts/login/")
@user_passes_test(is_seller, login_url="/accounts/login/")
def seller_delete_service(request, service_id):
    if request.method != "POST":
        return redirect("seller-services")

    seller = Seller.objects.filter(user=request.user).first()

    if seller is None:
        return redirect("seller-services")

    service = get_object_or_404(
        Service,
        id=service_id,
        seller=seller,
    )

    image_name = service.image.name if service.image else None

    try:
        service.delete()

        if image_name:
            service.image.storage.delete(image_name)

        messages.success(request, "Service deleted successfully!")

    except Exception:
        messages.error(
            request,
            "Unable to delete this service. Please try again.",
        )

    return redirect("seller-services")



@login_required(login_url="/accounts/login/")
@user_passes_test(is_seller, login_url="/accounts/login/")
def seller_packages(request):
    seller = Seller.objects.filter(user=request.user).first()

    packages = CatalogPackage.objects.none()

    if seller:
        packages = (
            CatalogPackage.objects
            .filter(seller=seller, is_deleted=False)
            .select_related("event")
            .prefetch_related("package_items__service")
            .order_by("-created_at")
        )

    return render(
        request,
        "sellers/seller_packages.html",
        {"packages": packages},
    )


@login_required(login_url="/accounts/login/")
@user_passes_test(is_seller, login_url="/accounts/login/")
def seller_create_package(request):
    seller = Seller.objects.filter(user=request.user).first()

    if seller is None:
        messages.error(request, "Your seller profile was not found.")
        return redirect("seller-packages")

    form = SellerCatalogPackageForm(
        request.POST or None,
    )

    if request.method == "POST" and form.is_valid():
        selected_services = form.cleaned_data["services"]
        service_prices = {}
        errors = []

        for service in selected_services:
            raw_price = request.POST.get(
                f"price_{service.pk}", ""
            ).strip()

            try:
                price = Decimal(raw_price)

                if (
                    not price.is_finite()
                    or price < 0
                    or price.as_tuple().exponent < -2
                ):
                    raise InvalidOperation

                service_prices[service.pk] = price

            except (InvalidOperation, ValueError):
                errors.append(
                    f"Enter a valid price for {service.name} "
                    "(zero or more, with at most two decimal places)."
                )

        if errors:
            for error in errors:
                form.add_error(None, error)
        else:
            try:
                with transaction.atomic():
                    package = form.save(commit=False)
                    package.seller = seller
                    package.save()

                    for service in selected_services:
                        CatalogPackageItem.objects.create(
                            package=package,
                            service=service,
                            selected_price=service_prices[service.pk],
                        )

                messages.success(
                    request, "Package created successfully!"
                )
                return redirect("seller-packages")

            except Exception:
                messages.error(
                    request,
                    "The package could not be saved. Please try again.",
                )

    return render(
        request,
        "sellers/seller_package_form.html",
        {"form": form, "package": None},
    )


@login_required(login_url="/accounts/login/")
@user_passes_test(is_seller, login_url="/accounts/login/")
def seller_view_package(request, package_id):
    seller = get_object_or_404(Seller, user=request.user)

    package = get_object_or_404(
        CatalogPackage.objects
        .filter(is_deleted=False)
        .select_related("event")
        .prefetch_related("package_items__service"),
        pk=package_id,
        seller=seller,
    )

    return render(
        request,
        "sellers/seller_package_detail.html",
        {"package": package},
    )


@login_required(login_url="/accounts/login/")
@user_passes_test(is_seller, login_url="/accounts/login/")
def seller_edit_package(request, package_id):
    seller = get_object_or_404(Seller, user=request.user)

    package = get_object_or_404(
        CatalogPackage.objects.filter(is_deleted=False).prefetch_related(
            "package_items__service"
        ),
        pk=package_id,
        seller=seller,
    )

    if request.method == "POST":
        form = SellerCatalogPackageForm(
            request.POST,
            instance=package,
        )
    else:
        form = SellerCatalogPackageForm(
            instance=package,
        )
        form.fields["services"].initial = [
            item.service_id for item in package.package_items.all()
        ]

    if request.method == "POST" and form.is_valid():
        selected_services = form.cleaned_data["services"]
        service_prices = {}
        errors = []

        for service in selected_services:
            raw_price = request.POST.get(
                f"price_{service.pk}", ""
            ).strip()

            try:
                price = Decimal(raw_price)

                if (
                    not price.is_finite()
                    or price < 0
                    or price.as_tuple().exponent < -2
                ):
                    raise InvalidOperation

                service_prices[service.pk] = price

            except (InvalidOperation, ValueError):
                errors.append(
                    f"Enter a valid price for {service.name}."
                )

        if errors:
            for error in errors:
                form.add_error(None, error)
        else:
            with transaction.atomic():
                package = form.save(commit=False)
                package.seller = seller
                package.save()

                package.package_items.all().delete()

                for service in selected_services:
                    CatalogPackageItem.objects.create(
                        package=package,
                        service=service,
                        selected_price=service_prices[service.pk],
                    )

            messages.success(request, "Package updated successfully!")
            return redirect("seller-packages")

    existing_prices = {
        str(item.service_id): str(item.selected_price)
        for item in package.package_items.all()
    }

    return render(
        request,
        "sellers/seller_package_form.html",
        {
            "form": form,
            "package": package,
            "existing_prices": existing_prices,
        },
    )


@login_required(login_url="/accounts/login/")
@user_passes_test(is_seller, login_url="/accounts/login/")
def seller_delete_package(request, package_id):
    if request.method != "POST":
        return redirect("seller-packages")

    seller = get_object_or_404(Seller, user=request.user)

    package = get_object_or_404(
        CatalogPackage,
        pk=package_id,
        seller=seller,
        is_deleted=False,
    )

    package.is_deleted = True
    package.save(update_fields=["is_deleted"])
    messages.success(request, "Package deleted successfully!")

    return redirect("seller-packages")


@login_required(login_url="/accounts/login/")
@user_passes_test(is_seller, login_url="/accounts/login/")
def seller_profile(request):
    seller = get_object_or_404(
        Seller,
        user=request.user
    )

    if request.method == "POST":
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        business_name = request.POST.get("business_name", "").strip()
        phone = request.POST.get("phone", "").strip()
        address = request.POST.get("address", "").strip()

        if not business_name:
            messages.error(request, "Business name is required.")
        else:
            request.user.first_name = first_name
            request.user.last_name = last_name
            request.user.save(
                update_fields=["first_name", "last_name"]
            )

            seller.business_name = business_name
            seller.phone = phone
            seller.address = address
            seller.save(
                update_fields=["business_name", "phone", "address"]
            )

            messages.success(
                request,
                "Your profile has been updated successfully!"
            )

            return redirect("seller-profile")

    return render(
        request,
        "sellers/seller_profile.html",
        {"seller": seller}
    )
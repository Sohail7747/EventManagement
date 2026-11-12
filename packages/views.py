
from datetime import date
from decimal import Decimal, InvalidOperation
import calendar
from django.shortcuts import render, redirect
from django.db import transaction
from django.db.models import Avg, Count, Prefetch
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from bookings.models import ServiceReview
from admin_panel.models import Event, Seller, Service
from .models import (
    EventPackage,
    PackageService,
    CatalogPackage,
    CatalogPackageItem,
    ServiceQuote,
    ServiceQuoteRequest,
)
from .serializers import (
    EventOptionSerializer,
    ServiceOptionSerializer,
    EventPackageSerializer,
)

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.urls import reverse
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect, get_object_or_404

from .models import CatalogPackage
from .pricing import PACKAGE_GUEST_PRICE


@api_view(["POST"])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def package_builder_availability_api(request):
    if getattr(getattr(request.user, "profile", None), "role", None) != "USER":
        return Response(
            {"error": "Customer account required."},
            status=status.HTTP_403_FORBIDDEN,
        )

    categories = request.data.get("categories")
    if (
        not isinstance(categories, list)
        or not categories
        or len(categories) > 30
        or any(not isinstance(category, str) or not category.strip() for category in categories)
    ):
        return Response(
            {"error": "Choose at least one valid service."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        budget = Decimal(str(request.data.get("budget", "")))
        year, month = (
            int(value)
            for value in str(request.data.get("month", "")).split("-", 1)
        )
        month_start = date(year, month, 1)
        month_end = date(year, month, calendar.monthrange(year, month)[1])
    except (InvalidOperation, TypeError, ValueError):
        return Response(
            {"error": "A valid budget and month are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if (
        not budget.is_finite()
        or budget <= 0
        or budget > Decimal("999999999.99")
    ):
        return Response(
            {"error": "Enter a valid budget."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    categories = {value.strip().casefold() for value in categories}
    offering_prices = {}
    for service in Service.objects.filter(
        name__isnull=False,
        seller__isnull=False,
        is_deleted=False,
    ).select_related("seller"):
        category = service.name.strip().casefold()
        if category in categories:
            offering_prices.setdefault((category, service.seller_id), (
                service.price,
                "SERVICE",
            ))
    for package_item in CatalogPackageItem.objects.filter(
        package__is_deleted=False,
        package__event__is_deleted=False,
        package__seller__isnull=False,
        service__is_deleted=False,
    ).select_related("package", "service"):
        category = package_item.service.name.strip().casefold()
        if category not in categories:
            continue
        key = (category, package_item.package.seller_id)
        previous = offering_prices.get(key)
        if (
            previous is None
            or previous[1] == "SERVICE"
            or package_item.selected_price < previous[0]
        ):
            offering_prices[key] = (package_item.selected_price, "PACKAGE_ITEM")

    seller_ids = {
        seller_id
        for (_, seller_id), (price, _) in offering_prices.items()
        if price <= budget
    }

    from bookings.availability import unavailable_dates_for_sellers

    unavailable_by_seller = {
        seller_id: [
            unavailable_date.isoformat()
            for unavailable_date in unavailable_dates_for_sellers(
                [seller_id],
                month_start,
                month_end,
            )
        ]
        for seller_id in sorted(seller_ids)
    }
    return Response(
        {
            "month": month_start.strftime("%Y-%m"),
            "unavailable_by_seller": unavailable_by_seller,
        }
    )


def package_selection_page(request):
    """Build mix-and-match custom packages from seller service offerings."""
    if not request.user.is_authenticated:
        return redirect("accounts-login-page")
    if getattr(getattr(request.user, "profile", None), "role", None) != "USER":
        messages.error(request, "Package recommendations are available to customer accounts only.")
        return redirect("home")

    reviewed_services = (
        Service.objects.annotate(
            review_average=Avg("reviews__rating"),
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
    offerings_by_seller_and_service = {}

    def remember_offering(
        service,
        seller,
        selected_price,
        offer_type,
        offer_id,
    ):
        service_name = service.name.strip()
        normalized_name = service_name.casefold()
        if not normalized_name:
            return
        key = (normalized_name, seller.pk)
        candidate = {
            "category": normalized_name,
            "service_name": service_name,
            "service_id": service.pk,
            "seller_id": seller.pk,
            "seller_name": seller.business_name,
            "price": str(selected_price),
            "image_url": service.image.url if service.image else "",
            "offer_type": offer_type,
            "offer_id": offer_id,
            "rating_average": (
                str(service.review_average)
                if service.review_average is not None
                else ""
            ),
            "review_count": service.review_count,
            "reviews": [
                {
                    "rating": review.rating,
                    "comment": review.comment,
                    "reviewer": (
                        review.user.get_full_name()
                        or review.user.username
                    ),
                    "date": review.created_at.strftime("%d %b %Y"),
                }
                for review in service.reviews.all()[:3]
            ],
        }
        previous = offerings_by_seller_and_service.get(key)
        prefer_package_price = (
            offer_type == "PACKAGE_ITEM"
            and previous is not None
            and previous["offer_type"] == "SERVICE"
        )
        prefer_lower_package_price = (
            offer_type == "PACKAGE_ITEM"
            and previous is not None
            and previous["offer_type"] == "PACKAGE_ITEM"
            and selected_price < Decimal(previous["price"])
        )
        if (
            previous is None
            or prefer_package_price
            or prefer_lower_package_price
        ):
            offerings_by_seller_and_service[key] = candidate

    for service in (
        reviewed_services.filter(seller__isnull=False, is_deleted=False)
        .select_related("seller")
        .order_by("name", "seller__business_name", "pk")
    ):
        remember_offering(
            service,
            service.seller,
            service.price,
            "SERVICE",
            service.pk,
        )

    for package_item in (
        CatalogPackageItem.objects.filter(
            package__is_deleted=False,
            package__event__is_deleted=False,
            package__seller__isnull=False,
            service__is_deleted=False,
        )
        .select_related("package__seller")
        .prefetch_related(
            Prefetch("service", queryset=reviewed_services)
        )
        .order_by("service__name", "package__seller__business_name", "pk")
    ):
        remember_offering(
            package_item.service,
            package_item.package.seller,
            package_item.selected_price,
            "PACKAGE_ITEM",
            package_item.pk,
        )

    service_offerings = sorted(
        offerings_by_seller_and_service.values(),
        key=lambda offering: (
            offering["service_name"].casefold(),
            Decimal(offering["price"]),
            offering["seller_name"].casefold(),
        ),
    )
    service_names_by_category = {}
    for offering in service_offerings:
        service_names_by_category.setdefault(
            offering["category"],
            offering["service_name"],
        )
    service_names = sorted(
        service_names_by_category.items(),
        key=lambda category: category[1].casefold(),
    )

    requested_date = request.GET.get("event_date", "").strip()
    selected_date = None
    try:
        parsed_date = date.fromisoformat(requested_date) if requested_date else None
        if parsed_date and parsed_date >= timezone.localdate():
            selected_date = parsed_date
    except ValueError:
        pass

    return render(
        request,
        "packages/user_create_package.html",
        {
            "services": [
                {"name": name, "category": category}
                for category, name in service_names
            ],
            "service_offerings": service_offerings,
            "today": timezone.localdate(),
            "selected_date": selected_date,
            "guest_price": PACKAGE_GUEST_PRICE,
        },
    )


@login_required(login_url="/accounts/login/")
def request_service_quote(request):
    if request.method != "POST":
        return redirect("package-selection")
    if getattr(getattr(request.user, "profile", None), "role", None) != "USER":
        messages.error(request, "Quote requests are available to customer accounts only.")
        return redirect("home")

    service_name = str(request.POST.get("service_name", "")).strip()
    details = str(request.POST.get("details", "")).strip()
    requested_date = str(request.POST.get("event_date", "")).strip()
    if not service_name or len(service_name) > 200:
        messages.error(request, "Enter a service name of 200 characters or fewer.")
        return redirect("package-selection")
    if len(details) > 2000:
        messages.error(request, "Service request details must be 2,000 characters or fewer.")
        return redirect("package-selection")
    if Service.objects.filter(
        name__iexact=service_name,
        seller__isnull=False,
        is_deleted=False,
    ).exists():
        messages.error(
            request,
            "A seller already offers this service. Select it to see matching packages.",
        )
        return redirect("package-selection")

    event_date = None
    if requested_date:
        try:
            event_date = date.fromisoformat(requested_date)
        except ValueError:
            messages.error(request, "Choose a valid event date.")
            return redirect("package-selection")
        if event_date < timezone.localdate():
            messages.error(request, "The event date cannot be in the past.")
            return redirect("package-selection")

    sellers = list(Seller.objects.order_by("pk"))
    if not sellers:
        messages.error(request, "There are no sellers available to receive quote requests yet.")
        return redirect("package-selection")

    with transaction.atomic():
        quote_request = ServiceQuoteRequest.objects.create(
            customer=request.user,
            service_name=service_name,
            event_date=event_date,
            details=details,
        )
        ServiceQuote.objects.bulk_create(
            [
                ServiceQuote(request=quote_request, seller=seller)
                for seller in sellers
            ]
        )

    messages.success(
        request,
        "Your quote request has been sent to sellers. You can follow replies in My quote requests.",
    )
    return redirect("my-service-quotes")


@login_required(login_url="/accounts/login/")
def my_service_quotes_page(request):
    if getattr(getattr(request.user, "profile", None), "role", None) != "USER":
        messages.error(request, "Quote requests are available to customer accounts only.")
        return redirect("home")
    quote_requests = (
        ServiceQuoteRequest.objects.filter(customer=request.user)
        .prefetch_related("quotes__seller")
        .order_by("-created_at")
    )
    return render(
        request,
        "packages/my_service_quotes.html",
        {"quote_requests": quote_requests, "active_page": "quotes"},
    )


@login_required(login_url="/accounts/login/")
def my_custom_packages_page(request):
    if getattr(getattr(request.user, "profile", None), "role", None) != "USER":
        messages.error(request, "This section is available to customer accounts only.")
        return redirect("home")
    packages = (
        EventPackage.objects.filter(user=request.user)
        .select_related("event")
        .prefetch_related("package_services__service__seller")
        .order_by("-created_at")
    )
    return render(
        request,
        "packages/my_custom_packages.html",
        {"packages": packages, "active_page": "packages"},
    )

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def package_options_api(request):
    """Return available events and services."""
    if getattr(getattr(request.user, "profile", None), "role", None) != "USER":
        return Response(
            {"error": "Customer account required."},
            status=status.HTTP_403_FORBIDDEN,
        )

    events = Event.objects.filter(is_deleted=False).order_by("id")
    services = (
        Service.objects
        .filter(seller__isnull=False, is_deleted=False)
        .select_related("seller")
        .order_by("name", "seller__business_name")
    )

    return Response({
        "events": EventOptionSerializer(
            events,
            many=True,
            context={"request": request},
        ).data,
        "services": ServiceOptionSerializer(
            services,
            many=True,
        ).data,
    })


@api_view(["POST"])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def create_event_package_api(request):
    """Create a package for the authenticated customer."""
    if getattr(getattr(request.user, "profile", None), "role", None) != "USER":
        return Response(
            {"error": "Customer account required."},
            status=status.HTTP_403_FORBIDDEN,
        )

    event_date = request.data.get("event_date")
    event_end_date = request.data.get("event_end_date") or event_date
    package_title = str(request.data.get("package_title", "")).strip()[:200]
    selected_services = request.data.get("services")

    if not event_date:
        return Response(
            {"error": "An event date is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if "budget" not in request.data:
        return Response(
            {"error": "A budget is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not isinstance(selected_services, list) or not selected_services:
        return Response(
            {"error": "Please select at least one service."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        booking_date = date.fromisoformat(event_date)
        booking_end_date = date.fromisoformat(event_end_date)
    except (ValueError, TypeError):
        return Response(
            {"error": "Use a valid date in YYYY-MM-DD format."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        budget = Decimal(str(request.data["budget"]))
    except (InvalidOperation, TypeError, ValueError):
        return Response(
            {"error": "Enter a valid budget."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if (
        not budget.is_finite()
        or budget <= 0
        or budget > Decimal("999999999.99")
    ):
        return Response(
            {"error": "Enter a valid budget."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    raw_guest_count = request.data.get("guest_count", 1)
    try:
        guest_count_value = Decimal(str(raw_guest_count))
    except (InvalidOperation, TypeError, ValueError):
        return Response(
            {"error": "Enter a valid guest count between 1 and 500."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if (
        not guest_count_value.is_finite()
        or guest_count_value != guest_count_value.to_integral_value()
        or not 1 <= guest_count_value <= 500
    ):
        return Response(
            {"error": "Enter a valid guest count between 1 and 500."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    guest_count = int(guest_count_value)

    if booking_date < timezone.localdate() or booking_end_date < booking_date:
        return Response(
            {"error": "The booking date cannot be in the past."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    requested_offerings = []

    for item in selected_services:
        if not isinstance(item, dict) or not item.get("service_id"):
            return Response(
                {"error": "Each service needs a service_id."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            service_id = int(item["service_id"])
        except (TypeError, ValueError):
            return Response(
                {"error": "Each service needs a valid service_id."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if service_id < 1:
            return Response(
                {"error": "Each service needs a valid service_id."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        seller_id = item.get("seller_id")
        if seller_id is None and item.get("offer_type", "SERVICE") == "SERVICE":
            seller_id = (
                Service.objects.filter(
                    pk=service_id,
                    is_deleted=False,
                    seller__isnull=False,
                )
                .values_list("seller_id", flat=True)
                .first()
            )
        try:
            seller_id = int(seller_id)
        except (TypeError, ValueError):
            return Response(
                {"error": "Each service needs a valid seller offering."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        offer_type = item.get("offer_type", "SERVICE")
        offer_id = item.get("offer_id")
        try:
            offer_id = int(offer_id) if offer_id else service_id
        except (TypeError, ValueError):
            return Response(
                {"error": "Each service needs a valid seller offering."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if offer_type == "PACKAGE_ITEM":
            offering = (
                CatalogPackageItem.objects.filter(
                    pk=offer_id,
                    service_id=service_id,
                    package__seller_id=seller_id,
                    package__is_deleted=False,
                    package__event__is_deleted=False,
                    service__is_deleted=False,
                )
                .select_related("service", "package__seller")
                .first()
            )
            if offering is None:
                return Response(
                    {"error": "One or more selected services are unavailable."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            service = offering.service
            seller = offering.package.seller
            selected_price = offering.selected_price
        elif offer_type == "SERVICE":
            service = (
                Service.objects.filter(
                    pk=service_id,
                    seller_id=seller_id,
                    is_deleted=False,
                )
                .select_related("seller")
                .first()
            )
            if service is None or offer_id != service_id:
                return Response(
                    {"error": "One or more selected services are unavailable."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            seller = service.seller
            selected_price = service.price
        else:
            return Response(
                {"error": "Each service needs a valid seller offering."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        requested_offerings.append(
            (service, seller, selected_price)
        )

    from bookings.availability import (
        BookingUnavailableError,
        assert_dates_available,
    )

    try:
        assert_dates_available(
            [seller.pk for _, seller, _ in requested_offerings],
            booking_date,
            booking_end_date,
        )
    except BookingUnavailableError as error:
        return Response(
            {"error": str(error)},
            status=status.HTTP_409_CONFLICT,
        )

    offering_keys = [
        (service.name.strip().casefold(), seller.pk)
        for service, seller, _ in requested_offerings
    ]
    if len(offering_keys) != len(set(offering_keys)):
        return Response(
            {"error": "Choose only one service offer for each service category."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    service_categories = [
        service.name.strip().casefold()
        for service, _, _ in requested_offerings
    ]
    if len(service_categories) != len(set(service_categories)):
        return Response(
            {"error": "Choose only one seller offering for each service type."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        with transaction.atomic():
            package = EventPackage.objects.create(
                user=request.user,
                package_title=package_title,
                event_date=booking_date,
                event_end_date=booking_end_date,
                guest_count=guest_count,
                event_price=0,
                total_cost=0,
            )

            total = Decimal("0")

            for service, seller, selected_price in requested_offerings:
                if (
                    not selected_price.is_finite()
                    or selected_price < 0
                    or selected_price > Decimal("99999999.99")
                ):
                    raise ValueError(
                        "Service prices must be between 0 and 99,999,999.99."
                    )

                if selected_price.as_tuple().exponent < -2:
                    raise ValueError(
                        "Prices can have at most two decimal places."
                    )

                PackageService.objects.create(
                    package=package,
                    service=service,
                    seller=seller,
                    selected_price=selected_price,
                )

                total += selected_price

            if total > Decimal("9999999999.99"):
                raise ValueError("The total package price is too high.")
            if total > budget:
                raise ValueError(
                    "The selected services exceed your budget."
                )

            package.total_cost = total
            package.save(update_fields=["total_cost"])

    except ValueError as error:
        return Response(
            {"error": str(error)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    package = EventPackage.objects.select_related(
        "user", "event"
    ).prefetch_related(
        "package_services__service__seller",
        "package_services__seller",
    ).get(pk=package.pk)

    return Response(
        {
            "message": "Package created successfully.",
            "booking_url": reverse(
                "custom-package-booking",
                args=[package.pk],
            ),
            "package": EventPackageSerializer(
                package,
                context={"request": request},
            ).data,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_packages_api(request):
    """Return packages belonging only to the logged-in customer."""
    if getattr(getattr(request.user, "profile", None), "role", None) != "USER":
        return Response(
            {"error": "Customer account required."},
            status=status.HTTP_403_FORBIDDEN,
        )

    packages = EventPackage.objects.filter(
        user=request.user
    ).select_related(
        "event", "user"
    ).prefetch_related(
        "package_services__service__seller"
    ).order_by("-created_at")

    serializer = EventPackageSerializer(
        packages,
        many=True,
        context={"request": request},
    )

    return Response(serializer.data)




@staff_member_required
def catalog_package_detail(request, pk):
    package = get_object_or_404(
        CatalogPackage.objects
        .filter(is_deleted=False)
        .select_related("event", "seller", "seller__user")
        .prefetch_related("package_items__service"),
        pk=pk
    )

    return render(
        request,
        "packages/catalog_package_detail.html",
        {"package": package}
    )
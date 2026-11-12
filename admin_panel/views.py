from django.shortcuts import render
from django.db.models import Prefetch
from django.contrib.auth.models import User

from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response

from .models import Seller, Event, Service, StaticPage
from bookings.models import Booking
from .analytics import monthly_amounts, monthly_counts
from .serializers import AdminUserSerializer, AdminSellerSerializer
from packages.models import CatalogPackage, CatalogPackageItem, EventPackage
from payments.models import PackagePaymentAttempt, PayoutRequest, SellerEarning

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.views.decorators.http import require_POST

from .forms import EventForm, ServiceForm, StaticPageForm
from django.contrib.auth.decorators import login_required
from django.db.models import F, Sum
from decimal import Decimal


@permission_classes([IsAuthenticated])
def dashboard_page(request):
    packages = (
         CatalogPackage.objects
        .filter(is_deleted=False)
        .select_related("event", "seller", "seller__user")
        .prefetch_related("package_items__service")
        .order_by("-created_at")
    )

    return render(
        request,
        "dashboard/dashboard.html",
        {"packages": packages}
    )


def users_page(request):
    return render(request, "dashboard/users.html")


def sellers_home_page(request):
    return render(request, "sellers_home.html")

def sellers_page(request):
    return render(request, "dashboard/sellers.html")


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_api(request):
    if not request.user.is_staff:
        return Response(
            {"error": "Admin permission required."},
            status=status.HTTP_403_FORBIDDEN
        )

    return Response({
        "total_users": User.objects.count(),
        "total_sellers": Seller.objects.count(),
        "total_events": Event.objects.filter(is_deleted=False).count(),
        "total_services": Service.objects.filter(is_deleted=False).count(),
        "total_static_pages": StaticPage.objects.count(),
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def seller_home_api(request):
    user = request.user

    if user.is_staff:
        return Response(
            {"error": "Use the admin dashboard."},
            status=status.HTTP_403_FORBIDDEN
        )

    if not hasattr(user, "profile") or user.profile.role != "SELLER":
        return Response(
            {"error": "Seller permission required."},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        seller = user.seller_profile
    except Seller.DoesNotExist:
        return Response(
            {"error": "Seller profile not found."},
            status=status.HTTP_404_NOT_FOUND
        )

    return Response({
        "seller": {
            "id": seller.id,
            "business_name": seller.business_name,
            "phone": seller.phone,
            "address": seller.address,
        },
        "events": [
            {
                "id": event.id,
                "title": event.title,
                "location": event.location,
                "event_date": event.event_date.isoformat(),
                "price": str(event.price),
            }
            for event in seller.events.all()
        ],
        "services": [
            {
                "id": service.id,
                "name": service.name,
                "price": str(service.price),
            }
            for service in seller.services.all()
        ],
    }, status=status.HTTP_200_OK)


class AdminUserListCreateAPI(generics.ListCreateAPIView):
    queryset = User.objects.exclude(profile__role="SELLER").order_by("id")
    serializer_class = AdminUserSerializer
    permission_classes = [IsAdminUser]


class AdminUserDetailAPI(generics.RetrieveUpdateDestroyAPIView):
    queryset = User.objects.exclude(profile__role="SELLER")
    serializer_class = AdminUserSerializer
    permission_classes = [IsAdminUser]

    def destroy(self, request, *args, **kwargs):
        user_to_delete = self.get_object()

        if user_to_delete.is_superuser:
            return Response(
                {"error": "The main admin account cannot be deleted."},
                status=status.HTTP_403_FORBIDDEN
            )

        if user_to_delete.pk == request.user.pk:
            return Response(
                {"error": "You cannot delete your own account."},
                status=status.HTTP_403_FORBIDDEN
            )

        return super().destroy(request, *args, **kwargs)
    

from .models import Seller
from .serializers import AdminSellerSerializer


class AdminSellerListCreateAPI(generics.ListCreateAPIView):
    queryset = Seller.objects.select_related(
        "user", "user__profile"
    ).order_by("id")
    serializer_class = AdminSellerSerializer
    permission_classes = [IsAdminUser]


class AdminSellerDetailAPI(generics.RetrieveUpdateDestroyAPIView):
    queryset = Seller.objects.select_related(
        "user", "user__profile"
    )
    serializer_class = AdminSellerSerializer
    permission_classes = [IsAdminUser]

    def perform_destroy(self, instance):
        # Delete the seller business profile, not the login account.
        instance.delete()


@api_view(["GET"])
@permission_classes([IsAdminUser])
def seller_accounts_api(request):
    accounts = User.objects.filter(
        profile__role="SELLER",
        seller_profile__isnull=True
    ).order_by("id")

    return Response([
        {
            "id": account.id,
            "name": account.first_name or account.username,
            "email": account.email,
        }
        for account in accounts
    ])


def admin_check(user):
    return user.is_authenticated and user.is_staff

admin_required = user_passes_test(admin_check, login_url="/accounts/login/")


@login_required(login_url="/accounts/login/")
@user_passes_test(lambda user: user.is_staff, login_url="/accounts/login/")
def dashboard_page(request):
    packages = (
        CatalogPackage.objects
        .filter(is_deleted=False)
        .select_related("event", "seller", "seller__user")
        .prefetch_related("package_items__service")
        .order_by("-created_at")
    )
    earnings = SellerEarning.objects.all()
    gross_earnings = earnings.annotate(
        gross_amount=F("seller_amount") + F("commission_amount")
    )

    context = {
        "packages": packages,
        "packages_count": packages.count(),
        "users_count": User.objects.count(),
        "sellers_count": Seller.objects.count(),
        "events_count": Event.objects.filter(is_deleted=False).count(),
        "services_count": Service.objects.filter(is_deleted=False).count(),
        "static_pages_count": StaticPage.objects.count(),
        "bookings_count": Booking.objects.count(),
        "pending_bookings_count": Booking.objects.filter(
            status=Booking.Status.PENDING
        ).count(),
        "monthly_bookings": monthly_counts(Booking.objects.all()),
        "recent_bookings": (
            Booking.objects
            .select_related(
                "user",
                "seller",
                "event",
                "service",
                "catalog_package",
                "package_event",
                "package_event__seller",
                "payment_attempt",
            )
            .order_by("-created_at")[:6]
        ),
        "recent_events": (
            Event.objects
            .filter(is_deleted=False)
            .select_related("seller")
            .order_by("-created_at")[:5]
        ),
        "commission_total": SellerEarning.objects.aggregate(
            total=Sum("commission_amount")
        )["total"] or Decimal("0.00"),
        "payment_volume_total": gross_earnings.aggregate(
            total=Sum("gross_amount")
        )["total"] or Decimal("0.00"),
        "seller_payout_total": SellerEarning.objects.filter(
            payout_request__status=PayoutRequest.Status.PAID
        ).aggregate(total=Sum("seller_amount"))["total"] or Decimal("0.00"),
        "monthly_commissions": monthly_amounts(
            earnings,
            "commission_amount",
        ),
        "monthly_payment_volume": monthly_amounts(
            gross_earnings,
            "gross_amount",
        ),
        "monthly_users": monthly_counts(
            User.objects.all(),
            date_field="date_joined",
        ),
        "monthly_sellers": monthly_counts(Seller.objects.all()),
    }

    return render(request, "dashboard/dashboard.html", context)



# ---------------- EVENTS CRUD  ----------------

@admin_required
def events_page(request):
    events = (
        Event.objects
        .filter(is_deleted=False)
        .select_related("seller")
        .order_by("-id")
    )
    return render(request, "dashboard/events.html", {
        "events": events,
    })


@admin_required
def event_detail(request, pk):
    event = get_object_or_404(
        Event.objects.filter(is_deleted=False).select_related("seller"),
        pk=pk,
    )
    return render(request, "dashboard/event_detail.html", {
        "event": event,
    })


@admin_required
def event_create(request):
    if request.method == "POST":
        form = EventForm(request.POST, request.FILES)
        if form.is_valid():
            event = form.save(commit=False)
            event.price = Decimal("0.00")
            event.save()
            messages.success(request, "Event created successfully.")
            return redirect("admin-events")
    else:
        form = EventForm()

    return render(request, "dashboard/event_form.html", {
        "form": form,
        "editing_event": None,
        "page_title": "Add Event",
    })


@admin_required
def event_edit(request, pk):
    event = get_object_or_404(Event, pk=pk, is_deleted=False)

    if request.method == "POST":
        form = EventForm(request.POST, request.FILES, instance=event)
        if form.is_valid():
            form.save()
            messages.success(request, "Event updated successfully.")
            return redirect("admin-events")
    else:
        form = EventForm(instance=event)

    return render(request, "dashboard/event_form.html", {
        "form": form,
        "editing_event": event,
        "page_title": "Edit Event",
    })


@admin_required
@require_POST
def event_delete(request, pk):
    event = get_object_or_404(Event, pk=pk, is_deleted=False)
    event.is_deleted = True
    event.save(update_fields=["is_deleted"])
    messages.success(
        request,
        "Event removed from the catalog. Existing packages and bookings "
        "have been preserved.",
    )
    return redirect("admin-events")


# ---------------- SERVICES CRUD ----------------

@admin_required
def services_page(request):
    services = (
        Service.objects
        .filter(is_deleted=False)
        .select_related("seller")
        .order_by("-id")
    )
    return render(request, "dashboard/services.html", {
        "services": services,
    })

@admin_required
def service_detail(request, pk):
    service = get_object_or_404(
        Service.objects.select_related("seller"),
        pk=pk,
        is_deleted=False,
    )
    return render(request, "dashboard/service_detail.html", {
        "service": service,
    })


@admin_required
def service_create(request):
    if request.method == "POST":
        form = ServiceForm(request.POST, request.FILES)
        if form.is_valid():
            service = form.save(commit=False)
            service.price = Decimal("0.00")
            service.save()
            messages.success(request, "Service created successfully.")
            return redirect("admin-services")
    else:
        form = ServiceForm()

    return render(request, "dashboard/service_form.html", {
        "form": form,
        "editing_service": None,
        "page_title": "Add Service",
    })


@admin_required
def service_edit(request, pk):
    service = get_object_or_404(Service, pk=pk, is_deleted=False)

    if request.method == "POST":
        form = ServiceForm(
            request.POST,
            request.FILES,
            instance=service,
        )
        if form.is_valid():
            form.save()
            messages.success(request, "Service updated successfully.")
            return redirect("admin-services")
    else:
        form = ServiceForm(instance=service)

    return render(request, "dashboard/service_form.html", {
        "form": form,
        "editing_service": service,
        "page_title": "Edit Service",
    })


@admin_required
@require_POST
def service_delete(request, pk):
    service = get_object_or_404(Service, pk=pk, is_deleted=False)
    service.is_deleted = True
    service.save(update_fields=["is_deleted"])
    messages.success(
        request,
        "Service removed from the catalog. Existing package and booking "
        "records have been preserved.",
    )
    return redirect("admin-services")


# ---------------- STATIC PAGES CRUD ----------------

@admin_required
def static_pages_page(request):
    pages = StaticPage.objects.order_by("title")
    return render(request, "dashboard/static_pages.html", {
        "pages": pages,
    })


@admin_required
def static_page_detail(request, pk):
    page = get_object_or_404(StaticPage, pk=pk)
    return render(request, "dashboard/static_page_detail.html", {
        "page": page,
    })


@admin_required
def static_page_create(request):
    if request.method == "POST":
        form = StaticPageForm(request.POST)
        if form.is_valid():
            page = form.save()
            messages.success(request, "Static page created successfully.")
            return redirect("static-page-detail", pk=page.pk)
    else:
        form = StaticPageForm()

    return render(request, "dashboard/static_page_form.html", {
        "form": form,
        "editing_page": None,
        "page_title": "Add Static Page",
    })


@admin_required
def static_page_edit(request, pk):
    page = get_object_or_404(StaticPage, pk=pk)

    if request.method == "POST":
        form = StaticPageForm(request.POST, instance=page)
        if form.is_valid():
            form.save()
            messages.success(request, "Static page updated successfully.")
            return redirect("static-page-detail", pk=page.pk)
    else:
        form = StaticPageForm(instance=page)

    return render(request, "dashboard/static_page_form.html", {
        "form": form,
        "editing_page": page,
        "page_title": "Edit Static Page",
    })


@admin_required
@require_POST
def static_page_delete(request, pk):
    page = get_object_or_404(StaticPage, pk=pk)
    page.delete()
    messages.success(request, "Static page deleted successfully.")
    return redirect("admin-static-pages")



# ---------------- ADMIN CATALOG PACKAGES ----------------

@admin_required
def catalog_packages_page(request):
    packages = (
        CatalogPackage.objects
        .filter(is_deleted=False)
        .select_related("event", "seller", "seller__user")
        .prefetch_related(
            "package_items__service"
        )
        .order_by("-created_at")
    )
    custom_packages = (
        EventPackage.objects
        .select_related("user", "event", "event__seller")
        .prefetch_related(
            "package_services__service__seller",
            Prefetch(
                "payment_attempts",
                queryset=PackagePaymentAttempt.objects.order_by("-created_at"),
                to_attr="ordered_payment_attempts",
            ),
            "customer_bookings__seller_decisions__seller",
        )
        .order_by("-created_at")
    )

    return render(
        request,
        "dashboard/packages.html",
        {
            "packages": packages,
            "packages_count": packages.count(),
            "custom_packages": custom_packages,
        },
    )


@admin_required
def admin_catalog_package_detail(request, pk):
    package = get_object_or_404(
        CatalogPackage.objects
        .filter(is_deleted=False)
        .select_related("event", "seller", "seller__user")
        .prefetch_related("package_items__service"),
        pk=pk,
    )

    return render(
        request,
        "dashboard/package_detail.html",
        {"package": package},
    )


@admin_required
@require_POST
def admin_catalog_package_delete(request, pk):
    package = get_object_or_404(
        CatalogPackage,
        pk=pk,
        is_deleted=False,
    )
    package_title = package.title

    package.is_deleted = True
    package.save(update_fields=["is_deleted"])

    messages.success(
        request,
        f'Package "{package_title}" deleted successfully.',
    )

    return redirect("admin-catalog-packages")
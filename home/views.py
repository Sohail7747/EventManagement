from django.shortcuts import render, redirect
from django.contrib import messages
from django.db.models import Avg, Count, Q
from django.core.paginator import Paginator

from bookings.models import Favourite
from dashboard.models import Event, Profile, Service, StaticPage
from packages.models import CatalogPackage
from .models import ContactMessage


def _package_favourite_context(user, packages):
    if not user.is_authenticated:
        return False, set()
    try:
        if user.profile.role != "USER":
            return False, set()
    except Profile.DoesNotExist:
        return False, set()

    package_ids = [package.pk for package in packages]
    favourite_ids = Favourite.objects.filter(
        user=user,
        catalog_package_id__in=package_ids,
    ).values_list("catalog_package_id", flat=True)
    return True, set(favourite_ids)


def home_page(request):
    events = (
        Event.objects
        .filter(is_deleted=False)
        .select_related("seller")
        .order_by("-created_at")[:10]
    )

    services = (
        Service.objects
        .filter(is_deleted=False)
        .select_related("seller")
        .order_by("-created_at")[:10]
    )

    packages = list(
        CatalogPackage.objects
        .filter(is_deleted=False)
        .exclude(package_items__service__is_deleted=True)
        .select_related("event", "seller")
        .prefetch_related("package_items__service")
        .annotate(
            rating_average=Avg("reviews__rating"),
            review_count=Count("reviews", distinct=True),
        )
        .order_by("-created_at")[:10]
    )
    can_favourite, favourite_package_ids = _package_favourite_context(
        request.user,
        packages,
    )

    return render(request, "home/home.html", {
        "events": events,
        "services": services,
        "packages": packages,
        "can_favourite": can_favourite,
        "favourite_package_ids": favourite_package_ids,
    })


def events_page(request):
    events = (
        Event.objects
        .filter(is_deleted=False)
        .select_related("seller")
        .order_by("-created_at")
    )

    return render(request, "home/events.html", {"events": events})


def services_page(request):
    services = (
        Service.objects
        .filter(is_deleted=False)
        .select_related("seller")
        .order_by("-created_at")
    )

    return render(request, "home/services.html", {"services": services})


def packages_page(request):
    search_query = request.GET.get("q", "").strip()[:100]
    event_id = request.GET.get("event", "").strip()
    packages = (
        CatalogPackage.objects
        .filter(is_deleted=False)
        .exclude(event__is_deleted=True)
        .exclude(package_items__service__is_deleted=True)
        .select_related("event", "seller")
        .prefetch_related("package_items__service")
        .annotate(
            rating_average=Avg("reviews__rating"),
            review_count=Count("reviews", distinct=True),
        )
    )

    if search_query:
        packages = packages.filter(
            Q(title__icontains=search_query)
            | Q(description__icontains=search_query)
            | Q(event__title__icontains=search_query)
            | Q(package_items__service__name__icontains=search_query)
        )
    if event_id.isdigit() and len(event_id) <= 19:
        selected_event_id = int(event_id)
        if selected_event_id <= 9223372036854775807:
            packages = packages.filter(event_id=selected_event_id)

    page_obj = Paginator(
        packages.annotate(
            rating_average=Avg("reviews__rating"),
            review_count=Count("reviews", distinct=True),
        ).distinct().order_by("-created_at"),
        12,
    ).get_page(request.GET.get("page"))
    page_range = page_obj.paginator.get_elided_page_range(page_obj.number)
    packages = list(page_obj.object_list)
    can_favourite, favourite_package_ids = _package_favourite_context(
        request.user,
        packages,
    )

    return render(request, "home/packages.html", {
        "packages": packages,
        "page_obj": page_obj,
        "page_range": page_range,
        "can_favourite": can_favourite,
        "favourite_package_ids": favourite_package_ids,
        "search_query": search_query,
        "selected_event": event_id,
        "events": Event.objects.filter(is_deleted=False).order_by("title"),
    })


def about_page(request):
    page = StaticPage.objects.filter(slug="about").first()
    return render(request, "home/about.html", {"page": page})


def contact_page(request):
    if request.method == "POST":
        if not request.user.is_authenticated:
            messages.error(
                request,
                "Please log in to your account before sending a message."
            )
            return redirect(f"/accounts/login/?next={request.path}")

        name = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip()
        subject = request.POST.get("subject", "").strip()
        message = request.POST.get("message", "").strip()

        if not all([name, email, subject, message]):
            messages.error(
                request,
                "Please fill in all fields."
            )
        else:
            ContactMessage.objects.create(
                name=name,
                email=email,
                subject=subject,
                message=message,
            )

            messages.success(
                request,
                "Thank you! Your message has been sent successfully."
            )
            return redirect("contact")

    page = StaticPage.objects.filter(slug="contact").first()
    initial_name = ""
    initial_email = ""
    if request.user.is_authenticated:
        initial_name = request.user.get_full_name() or request.user.username
        initial_email = request.user.email or ""

    return render(
        request,
        "home/contact.html",
        {
            "page": page,
            "initial_name": initial_name,
            "initial_email": initial_email,
        },
    )
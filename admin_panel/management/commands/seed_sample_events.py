from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from admin_panel.models import Event


EVENTS = (
    (
        "Wedding Ceremony",
        "A beautifully styled wedding ceremony for family and friends.",
        "wedding-ceremony.jpg",
        "1587271636175-90d58cdad458",
        "Jaipur, Rajasthan",
    ),
    (
        "Wedding Reception",
        "An elegant evening reception with dinner, music, and celebration.",
        "wedding-reception.jpg",
        "1587271407850-8d438ca9fdf2",
        "Patna, Bihar",
    ),
    (
        "Birthday Celebration",
        "A colorful birthday celebration with decorations and refreshments.",
        "birthday-celebration.jpg",
        "1583875762487-5f8f7c718d14",
        "Delhi, India",
    ),
    (
        "Engagement Ceremony",
        "A special engagement gathering for the couple and their families.",
        "engagement-ceremony.jpg",
        "1520854221256-17451cc331bf",
        "Lucknow, Uttar Pradesh",
    ),
    (
        "Corporate Conference",
        "A professional conference setup for talks and team sessions.",
        "corporate-conference.jpg",
        "1540575467063-178a50c2df87",
        "Bengaluru, Karnataka",
    ),
    (
        "Product Launch",
        "A polished product launch with a stage and audience seating.",
        "product-launch.jpg",
        "1587825140708-dfaf72ae4b04",
        "Mumbai, Maharashtra",
    ),
    (
        "Live Music Concert",
        "A live concert experience with a stage, lights, and performers.",
        "live-music-concert.jpg",
        "1459749411175-04bf5292ceea",
        "Pune, Maharashtra",
    ),
    (
        "Baby Shower",
        "A warm baby shower gathering with thoughtful decorations.",
        "baby-shower.jpg",
        "1654894811891-3d291baaa011",
        "Patna, Bihar",
    ),
    (
        "Graduation Celebration",
        "A celebration honoring graduates and their achievements.",
        "graduation-celebration.jpg",
        "1541339907198-e08756dedf3f",
        "Kolkata, West Bengal",
    ),
    (
        "Haldi Ceremony",
        "A joyful haldi ceremony with traditional colors and decor.",
        "haldi-ceremony.jpg",
        "1653821355736-0c2598d0a63e",
        "Varanasi, Uttar Pradesh",
    ),
    (
        "Mehndi Ceremony",
        "A festive mehndi gathering with henna, music, and family.",
        "mehndi-ceremony.jpg",
        "1505932794465-147d1f1b2c97",
        "Jaipur, Rajasthan",
    ),
    (
        "Sangeet Night",
        "A lively evening of wedding music, dancing, and performances.",
        "sangeet-night.jpg",
        "1784202388318-a2caaeffe4b7",
        "Delhi, India",
    ),
    (
        "Anniversary Dinner",
        "An intimate anniversary dinner with a refined event setup.",
        "anniversary-dinner.jpg",
        "1712764995305-75422fbe0ecc",
        "Chandigarh, India",
    ),
    (
        "Music Festival",
        "An outdoor festival with live performances and a festive crowd.",
        "music-festival.jpg",
        "1514525253161-7a46d19cd819",
        "Goa, India",
    ),
    (
        "Gala Dinner",
        "A formal gala dinner for guests, teams, or special occasions.",
        "gala-dinner.jpg",
        "1533120921505-7f40f5237ee1",
        "Hyderabad, Telangana",
    ),
)

UNSPLASH_LICENSE_URL = "https://unsplash.com/license"


class Command(BaseCommand):
    help = "Create 15 shared sample events with locally stored photographs."

    def handle(self, *args, **options):
        image_directory = Path(settings.MEDIA_ROOT) / "events"
        image_directory.mkdir(parents=True, exist_ok=True)
        created_count = 0
        start_date = timezone.localdate() + timedelta(days=365)

        for index, event_data in enumerate(EVENTS):
            title, description, image_name, photo_id, location = event_data
            image_path = image_directory / image_name
            image_url = (
                f"https://images.unsplash.com/photo-{photo_id}"
                "?fit=crop&w=1400&q=85&fm=jpg"
            )
            if not image_path.is_file():
                request = Request(
                    image_url,
                    headers={"User-Agent": "EventSphere event catalog"},
                )
                with urlopen(request, timeout=30) as response:
                    content_type = response.headers.get("Content-Type", "")
                    image_data = response.read(15 * 1024 * 1024 + 1)

                if not content_type.startswith("image/"):
                    raise CommandError(
                        f"Expected an image for {title}, received "
                        f"{content_type or 'an unknown content type'}."
                    )
                if not image_data.startswith(b"\xff\xd8"):
                    raise CommandError(
                        f"The downloaded photograph for {title} is not a JPEG."
                    )
                if len(image_data) > 15 * 1024 * 1024:
                    raise CommandError(
                        f"The downloaded photograph for {title} is too large."
                    )

                image_path.write_bytes(image_data)

            event, created = Event.objects.get_or_create(
                title=title,
                is_deleted=False,
                defaults={
                    "description": description,
                    "image": f"events/{image_name}",
                    "location": location,
                    "event_date": start_date + timedelta(days=index),
                    "price": Decimal("0.00"),
                },
            )
            update_fields = []
            if event.description != description:
                event.description = description
                update_fields.append("description")
            if event.image.name != f"events/{image_name}":
                event.image = f"events/{image_name}"
                update_fields.append("image")
            if event.location != location:
                event.location = location
                update_fields.append("location")
            if update_fields:
                event.save(update_fields=update_fields)
            created_count += int(created)

        sources_path = image_directory / "IMAGE_SOURCES.txt"
        source_lines = [
            "Event catalog photographs downloaded from Unsplash.",
            f"License: {UNSPLASH_LICENSE_URL}",
            "",
        ]
        source_lines.extend(
            f"{image_name}: https://images.unsplash.com/photo-{photo_id}"
            for _, _, image_name, photo_id, _ in EVENTS
        )
        sources_path.write_text("\n".join(source_lines) + "\n", encoding="utf-8")

        self.stdout.write(
            self.style.SUCCESS(
                f"Ready: {len(EVENTS)} sample events "
                f"({created_count} newly added) with photographs in "
                "media/events/."
            )
        )

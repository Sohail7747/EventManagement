from decimal import Decimal
from pathlib import Path
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from dashboard.models import Service


SERVICES = (
    (
        "Catering",
        "Custom menus and catering service for celebrations.",
        "catering.jpg",
        "1555244162-803834f70033",
    ),
    (
        "Photography",
        "Professional photography to capture important moments.",
        "photography.jpg",
        "1549981832-2ba2ee913334",
    ),
    (
        "Videography",
        "Event films and highlight videos, captured and edited.",
        "videography.jpg",
        "1629756048377-09540f52caa1",
    ),
    (
        "Floral Decoration",
        "Fresh floral arrangements for tables, stages, and venues.",
        "floral-decoration.jpg",
        "1469371670807-013ccf25f16a",
    ),
    (
        "Stage and Venue Decor",
        "Stage backdrops and venue styling for memorable events.",
        "stage-venue-decor.jpg",
        "1587271407850-8d438ca9fdf2",
    ),
    (
        "DJ and Sound",
        "DJs and sound equipment to keep celebrations lively.",
        "dj-sound.jpg",
        "1470225620780-dba8ba36b745",
    ),
    (
        "Event Lighting",
        "Ambient, stage, and decorative lighting for your venue.",
        "event-lighting.jpg",
        "1514525253161-7a46d19cd819",
    ),
    (
        "Bridal Makeup",
        "Professional makeup services for weddings and events.",
        "bridal-makeup.jpg",
        "1587271315307-eaebc181c749",
    ),
    (
        "Mehndi Artist",
        "Intricate henna designs for weddings and celebrations.",
        "mehndi-artist.jpg",
        "1505932794465-147d1f1b2c97",
    ),
    (
        "Wedding Cake",
        "Custom celebration cakes designed for your occasion.",
        "wedding-cake.jpg",
        "1535254973040-607b474cb50d",
    ),
    (
        "Live Music",
        "Live musicians and performers for special occasions.",
        "live-music.jpg",
        "1499364615650-ec38552f4f34",
    ),
    (
        "Event Transportation",
        "Comfortable transportation for event guests and hosts.",
        "event-transportation.jpg",
        "1516536900061-d881b27e8ff8",
    ),
)

UNSPLASH_LICENSE_URL = "https://unsplash.com/license"


class Command(BaseCommand):
    help = "Create 12 shared sample services with locally stored photographs."

    def handle(self, *args, **options):
        image_directory = Path(settings.MEDIA_ROOT) / "services"
        image_directory.mkdir(parents=True, exist_ok=True)
        created_count = 0

        for name, description, image_name, photo_id in SERVICES:
            image_path = image_directory / image_name
            image_url = (
                f"https://images.unsplash.com/photo-{photo_id}"
                "?fit=crop&w=1400&q=85&fm=jpg"
            )
            if not image_path.is_file():
                request = Request(
                    image_url,
                    headers={"User-Agent": "EventSphere service catalog"},
                )
                with urlopen(request, timeout=30) as response:
                    content_type = response.headers.get("Content-Type", "")
                    image_data = response.read(15 * 1024 * 1024 + 1)

                if not content_type.startswith("image/"):
                    raise CommandError(
                        f"Expected an image for {name}, received "
                        f"{content_type or 'an unknown content type'}."
                    )
                if not image_data.startswith(b"\xff\xd8"):
                    raise CommandError(
                        f"The downloaded photograph for {name} is not a JPEG."
                    )
                if len(image_data) > 15 * 1024 * 1024:
                    raise CommandError(
                        f"The downloaded photograph for {name} is too large."
                    )

                image_path.write_bytes(image_data)

            service, created = Service.objects.get_or_create(
                name=name,
                is_deleted=False,
                defaults={
                    "description": description,
                    "image": f"services/{image_name}",
                    "price": Decimal("0.00"),
                },
            )
            update_fields = []
            if service.description != description:
                service.description = description
                update_fields.append("description")
            if service.image.name != f"services/{image_name}":
                service.image = f"services/{image_name}"
                update_fields.append("image")
            if update_fields:
                service.save(update_fields=update_fields)
            created_count += int(created)

        sources_path = image_directory / "IMAGE_SOURCES.txt"
        source_lines = [
            "Service catalog photographs downloaded from Unsplash.",
            f"License: {UNSPLASH_LICENSE_URL}",
            "",
        ]
        source_lines.extend(
            f"{image_name}: https://images.unsplash.com/photo-{photo_id}"
            for _, _, image_name, photo_id in SERVICES
        )
        sources_path.write_text("\n".join(source_lines) + "\n", encoding="utf-8")

        self.stdout.write(
            self.style.SUCCESS(
                f"Ready: {len(SERVICES)} sample services "
                f"({created_count} newly added) with photographs in "
                "media/services/."
            )
        )

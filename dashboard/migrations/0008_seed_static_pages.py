from django.db import migrations


STATIC_PAGES = [
    {
        "title": "About Us",
        "slug": "about",
        "content": (
            "EventSphere is designed to make discovering event services and "
            "curated packages easier. Whether you're planning a wedding, a "
            "family celebration, or a special gathering, we're here to help "
            "you explore your options.\n\n"
            "Our platform brings event listings, professional services, and "
            "thoughtfully assembled packages together in one place. Our goal "
            "is to make planning simpler so you can focus on the moments that "
            "matter."
        ),
    },
    {
        "title": "Contact Us",
        "slug": "contact",
        "content": (
            "Have a question about EventSphere or need help getting started? "
            "Send us a message using the form."
        ),
    },
]


def create_default_static_pages(apps, schema_editor):
    StaticPage = apps.get_model("dashboard", "StaticPage")
    for page in STATIC_PAGES:
        StaticPage.objects.get_or_create(
            slug=page["slug"],
            defaults=page,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("dashboard", "0007_profile_city_profile_profile_photo"),
    ]

    operations = [
        migrations.RunPython(
            create_default_static_pages,
            reverse_code=migrations.RunPython.noop,
        ),
    ]

from datetime import date, datetime, time

from django.db.models import Count, Sum
from django.utils import timezone


def monthly_counts(queryset, months=6, date_field="created_at"):
    current_month = timezone.localdate().replace(day=1)
    first_month_index = (
        current_month.year * 12 + current_month.month - months + 1
    )
    chart_months = []

    for offset in range(months):
        month_index = first_month_index + offset
        year, zero_based_month = divmod(month_index, 12)
        month = date(year, zero_based_month + 1, 1)
        chart_months.append(month)

    start_at = datetime.combine(chart_months[0], time.min)
    if timezone.is_aware(timezone.now()):
        start_at = timezone.make_aware(start_at)

    year_field = f"{date_field}__year"
    month_field = f"{date_field}__month"
    totals = {
        (entry[year_field], entry[month_field]): entry["total"]
        for entry in (
            queryset.filter(**{f"{date_field}__gte": start_at})
            .values(year_field, month_field)
            .annotate(total=Count("pk"))
        )
    }
    highest_total = max(totals.values(), default=0)

    return [
        {
            "label": month.strftime("%b"),
            "count": totals.get((month.year, month.month), 0),
            "height": (
                max(
                    6,
                    round(
                        totals.get((month.year, month.month), 0)
                        * 100
                        / highest_total
                    ),
                )
                if highest_total
                else 6
            ),
        }
        for month in chart_months
    ]


def monthly_amounts(queryset, amount_field, months=6):
    current_month = timezone.localdate().replace(day=1)
    first_month_index = (
        current_month.year * 12 + current_month.month - months + 1
    )
    chart_months = []
    for offset in range(months):
        month_index = first_month_index + offset
        year, zero_based_month = divmod(month_index, 12)
        chart_months.append(date(year, zero_based_month + 1, 1))

    start_at = datetime.combine(chart_months[0], time.min)
    if timezone.is_aware(timezone.now()):
        start_at = timezone.make_aware(start_at)

    totals = {
        (entry["created_at__year"], entry["created_at__month"]): entry["total"]
        for entry in (
            queryset.filter(created_at__gte=start_at)
            .values("created_at__year", "created_at__month")
            .annotate(total=Sum(amount_field))
        )
    }
    highest_total = max(totals.values(), default=0)

    return [
        {
            "label": month.strftime("%b"),
            "amount": totals.get((month.year, month.month), 0),
            "height": (
                max(
                    6,
                    round(
                        totals.get((month.year, month.month), 0)
                        * 100
                        / highest_total
                    ),
                )
                if highest_total
                else 6
            ),
        }
        for month in chart_months
    ]

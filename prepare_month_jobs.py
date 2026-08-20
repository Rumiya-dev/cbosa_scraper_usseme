import calendar
from datetime import date, timedelta

from database import (
    create_database,
    create_search_jobs_table,
    create_search_job,
    show_search_jobs,
)


# ============================================================
# TESTOWY ZAKRES
# ============================================================

# Пока специально создаём ТОЛЬКО два месяца.
#
# Мы ещё не создаём очередь на десятки лет.

START_DATE = date(
    2026,
    6,
    1
)

END_DATE = date(
    2026,
    7,
    31
)


# ============================================================
# GENERATOR MIESIĘCY
# ============================================================

def generate_month_ranges(
    start_date,
    end_date
):
    """
    Dzieli duży zakres na miesiące.

    Przykład:

    2026-06-01 -> 2026-06-30
    2026-07-01 -> 2026-07-31
    """

    current = start_date

    while current <= end_date:

        year = current.year
        month = current.month

        # Ile dni ma ten miesiąc?
        last_day_number = (
            calendar.monthrange(
                year,
                month
            )[1]
        )

        month_end = date(
            year,
            month,
            last_day_number
        )

        # Jeśli cały zakres kończy się
        # wcześniej niż miesiąc,
        # nie wychodzimy poza END_DATE.
        if month_end > end_date:

            month_end = end_date

        yield (
            current,
            month_end
        )

        current = (
            month_end
            + timedelta(days=1)
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "========================================"
    )

    print(
        "PRZYGOTOWANIE MIESIĘCZNYCH JOBÓW"
    )

    print(
        "========================================"
    )

    create_database()

    create_search_jobs_table()

    new_jobs = 0
    existing_jobs = 0

    for date_from, date_to in (
        generate_month_ranges(
            START_DATE,
            END_DATE
        )
    ):

        date_from_text = (
            date_from.isoformat()
        )

        date_to_text = (
            date_to.isoformat()
        )

        inserted = create_search_job(
            date_from_text,
            date_to_text
        )

        if inserted:

            new_jobs += 1

            status_text = "NOWY"

        else:

            existing_jobs += 1

            status_text = "JUŻ ISTNIEJE"

        print(
            date_from_text,
            "->",
            date_to_text,
            status_text
        )

    print(
        "\n========================================"
    )

    print(
        "PODSUMOWANIE"
    )

    print(
        "========================================"
    )

    print(
        "Nowych:",
        new_jobs
    )

    print(
        "Już istniejących:",
        existing_jobs
    )

    print(
        "\nSEARCH JOBS:"
    )

    for row in show_search_jobs():

        print(
            row
        )


if __name__ == "__main__":
    main()
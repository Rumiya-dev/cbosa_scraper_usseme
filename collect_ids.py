import time

from cbosa_client import (
    open_cbosa,
    search_documents,
    extract_search_info,
    extract_document_links,
    download_result_page,
)

from database import (
    create_database,
    add_documents,
    count_documents,
    count_by_status,
)


# ============================================================
# USTAWIENIA TESTU
# ============================================================

DATE_FROM = "2026-08-01"
DATE_TO = "2026-08-10"

# Пока только первые 3 страницы.
MAX_PAGES = 3

# Пауза между страницами.
PAGE_DELAY = 5


def main():

    print(
        "========================================"
    )

    print(
        "CBOSA - ZBIERANIE ID DO SQLITE"
    )

    print(
        "========================================"
    )

    # ========================================================
    # 1. Создаём SQLite
    # ========================================================

    print(
        "\n1. TWORZĘ / OTWIERAM BAZĘ"
    )

    create_database()

    print(
        "Baza SQLite gotowa."
    )

    # ========================================================
    # 2. Открываем CBOSA
    # ========================================================

    print(
        "\n2. OTWIERAM CBOSA"
    )

    open_cbosa()

    print(
        "CBOSA otwarta."
    )

    time.sleep(2)

    # ========================================================
    # 3. Выполняем поиск
    # ========================================================

    print(
        "\n3. WYSZUKUJĘ ORZECZENIA"
    )

    print(
        f"Zakres: {DATE_FROM} -> {DATE_TO}"
    )

    first_page_html = (
        search_documents(
            DATE_FROM,
            DATE_TO
        )
    )

    # ========================================================
    # 4. Узнаём количество страниц
    # ========================================================

    info = extract_search_info(
        first_page_html
    )

    total_documents = (
        info["total_documents"]
    )

    total_pages = (
        info["total_pages"]
    )

    print(
        "\nZnaleziono wszystkich:",
        total_documents
    )

    print(
        "Liczba stron:",
        total_pages
    )

    # ========================================================
    # 5. Для теста ограничиваемся тремя страницами
    # ========================================================

    pages_to_process = min(
        MAX_PAGES,
        total_pages
    )

    print(
        "\nW tym teście pobiorę tylko:",
        pages_to_process,
        "strony"
    )

    print(
        "Czyli maksymalnie:",
        pages_to_process * 10,
        "głównych orzeczeń."
    )

    total_new = 0
    total_existing = 0

    # ========================================================
    # 6. Перебираем страницы
    # ========================================================

    for page_number in range(
        1,
        pages_to_process + 1
    ):

        print(
            "\n========================================"
        )

        print(
            f"STRONA {page_number}/"
            f"{pages_to_process}"
        )

        print(
            "========================================"
        )

        # Первая страница у нас уже есть
        # из POST /cbo/search.
        if page_number == 1:

            html = first_page_html

        else:

            html = (
                download_result_page(
                    page_number
                )
            )

        # ----------------------------------------------------
        # Достаём основные ссылки.
        # ----------------------------------------------------

        links = extract_document_links(
            html
        )

        print(
            "Głównych linków:",
            len(links)
        )

        # ----------------------------------------------------
        # Записываем их в SQLite.
        # ----------------------------------------------------

        new_count, existing_count = (
            add_documents(
                links
            )
        )

        print(
            "Nowych:",
            new_count
        )

        print(
            "Już istniało:",
            existing_count
        )

        total_new += new_count
        total_existing += existing_count

        # ----------------------------------------------------
        # Пауза, кроме последней страницы.
        # ----------------------------------------------------

        if page_number < pages_to_process:

            print(
                f"Czekam {PAGE_DELAY} sek..."
            )

            time.sleep(
                PAGE_DELAY
            )

    # ========================================================
    # 7. Итог
    # ========================================================

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
        "Nowych w tym uruchomieniu:",
        total_new
    )

    print(
        "Już istniejących:",
        total_existing
    )

    print(
        "Wszystkich rekordów w bazie:",
        count_documents()
    )

    print(
        "Pending:",
        count_by_status(
            "pending"
        )
    )

    print(
        "Done:",
        count_by_status(
            "done"
        )
    )

    print(
        "Failed:",
        count_by_status(
            "failed"
        )
    )


if __name__ == "__main__":
    main()
import time

from cbosa_client import (
    open_cbosa,
    reset_session,
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

    create_search_jobs_table,
    get_or_create_search_job,
    update_search_total_pages,
    update_search_next_page,
    mark_search_job_done,
    mark_search_job_error,
    show_search_jobs,
)


# ============================================================
# USTAWIENIA
# ============================================================

DATE_FROM = "2026-08-01"
DATE_TO = "2026-08-10"


# Мы уже вручную собрали страницы 1-3.
#
# Поэтому для НОВОГО checkpoint-теста
# начинаем сразу со страницы 4.
#
# В настоящем новом диапазоне потом будет 1.
START_PAGE_FOR_NEW_JOB = 4


# За один запуск обрабатываем только 3 страницы.
#
# Это специально для проверки resume.
PAGES_PER_RUN = 3


# Пауза между страницами.
PAGE_DELAY = 5


# ============================================================
# PRZYWRACANIE KONTEKSTU WYSZUKIWANIA
# ============================================================

def restore_search_context():
    """
    Tworzy świeżą sesję CBOSA
    i ponownie wykonuje nasze wyszukiwanie.

    Jest to ważne, ponieważ /cbo/find?p=X
    zależy od aktywnej sesji wyszukiwarki.
    """

    print(
        "\nPrzywracam kontekst wyszukiwania..."
    )

    reset_session()

    open_cbosa()

    time.sleep(2)

    first_page_html = search_documents(
        DATE_FROM,
        DATE_TO
    )

    print(
        "Kontekst wyszukiwania przywrócony."
    )

    return first_page_html


# ============================================================
# POBRANIE I WALIDACJA STRONY
# ============================================================

def get_valid_result_page(
    page_number,
    first_page_html
):
    """
    Pobiera konkretną stronę.

    Następnie sprawdza, czy serwer naprawdę
    zwrócił właśnie tę stronę.

    Jeśli sesja CBOSA została utracona,
    odtwarza wyszukiwanie i próbuje jeszcze raz.
    """

    # --------------------------------------------------------
    # Страница №1 уже есть после POST /search.
    # --------------------------------------------------------

    if page_number == 1:

        html = first_page_html

    else:

        html = download_result_page(
            page_number
        )

    # --------------------------------------------------------
    # Проверяем номер страницы в самом HTML.
    # --------------------------------------------------------

    try:

        info = extract_search_info(
            html
        )

        current_page = (
            info["current_page"]
        )

    except Exception:

        current_page = None

    # --------------------------------------------------------
    # Всё правильно.
    # --------------------------------------------------------

    if current_page == page_number:

        return html

    # --------------------------------------------------------
    # Иначе сервер потерял контекст поиска.
    # Восстанавливаем его.
    # --------------------------------------------------------

    print(
        "\nUWAGA:"
    )

    print(
        "Serwer nie zwrócił oczekiwanej strony."
    )

    print(
        "Oczekiwano:",
        page_number
    )

    print(
        "Otrzymano:",
        current_page
    )

    new_first_page = (
        restore_search_context()
    )

    if page_number == 1:

        html = new_first_page

    else:

        html = download_result_page(
            page_number
        )

    # --------------------------------------------------------
    # Проверяем ещё раз.
    # --------------------------------------------------------

    info = extract_search_info(
        html
    )

    if (
        info["current_page"]
        != page_number
    ):

        raise RuntimeError(
            f"Nie udało się pobrać "
            f"strony {page_number}. "
            f"Serwer zwrócił stronę "
            f"{info['current_page']}."
        )

    return html


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "========================================"
    )

    print(
        "CBOSA - COLLECTOR Z CHECKPOINTEM"
    )

    print(
        "========================================"
    )

    # ========================================================
    # 1. БАЗА
    # ========================================================

    create_database()

    create_search_jobs_table()

    # ========================================================
    # 2. ЧИТАЕМ ИЛИ СОЗДАЁМ CHECKPOINT
    # ========================================================

    job = get_or_create_search_job(
        DATE_FROM,
        DATE_TO,
        start_page=START_PAGE_FOR_NEW_JOB,
    )

    (
        job_id,
        date_from,
        date_to,
        next_page,
        saved_total_pages,
        status,
    ) = job

    print(
        "\n========================================"
    )

    print(
        "CHECKPOINT"
    )

    print(
        "========================================"
    )

    print(
        "Job ID:",
        job_id
    )

    print(
        "Zakres:",
        date_from,
        "->",
        date_to
    )

    print(
        "Następna strona:",
        next_page
    )

    print(
        "Zapisana liczba stron:",
        saved_total_pages
    )

    print(
        "Status:",
        status
    )

    # ========================================================
    # 3. ОТКРЫВАЕМ CBOSA
    # ========================================================

    print(
        "\nOtwieram CBOSA..."
    )

    open_cbosa()

    time.sleep(2)

    # ========================================================
    # 4. ВСЕГДА ПОВТОРЯЕМ ПОИСК
    #
    # Даже если checkpoint уже существует.
    #
    # Нам нужно восстановить серверную сессию поиска.
    # ========================================================

    print(
        "\nOdtwarzam wyszukiwanie..."
    )

    first_page_html = (
        search_documents(
            DATE_FROM,
            DATE_TO
        )
    )

    search_info = extract_search_info(
        first_page_html
    )

    total_pages = (
        search_info["total_pages"]
    )

    total_documents = (
        search_info["total_documents"]
    )

    update_search_total_pages(
        job_id,
        total_pages
    )

    print(
        "Wszystkich orzeczeń:",
        total_documents
    )

    print(
        "Wszystkich stron:",
        total_pages
    )

    # ========================================================
    # 5. Проверяем, не закончена ли уже работа.
    # ========================================================

    if next_page > total_pages:

        mark_search_job_done(
            job_id
        )

        print(
            "Ten zakres jest już zakończony."
        )

        return

    # ========================================================
    # 6. Определяем, где остановимся ЭТИМ запуском.
    # ========================================================

    last_page_this_run = min(
        next_page
        + PAGES_PER_RUN
        - 1,

        total_pages
    )

    print(
        "\nTen запуск обработает страницы:"
    )

    print(
        next_page,
        "->",
        last_page_this_run
    )

    total_new = 0
    total_existing = 0

    # ========================================================
    # 7. ЦИКЛ ПО СТРАНИЦАМ
    # ========================================================

    for page_number in range(
        next_page,
        last_page_this_run + 1
    ):

        print(
            "\n========================================"
        )

        print(
            f"STRONA {page_number}/"
            f"{total_pages}"
        )

        print(
            "========================================"
        )

        try:

            # ------------------------------------------------
            # Получаем правильную страницу.
            # ------------------------------------------------

            html = get_valid_result_page(
                page_number,
                first_page_html
            )

            # ------------------------------------------------
            # Извлекаем только основные решения.
            # ------------------------------------------------

            links = extract_document_links(
                html
            )

            print(
                "Głównych linków:",
                len(links)
            )

            # ------------------------------------------------
            # На всех страницах кроме последней
            # обычно должно быть 10 результатов.
            # ------------------------------------------------

            if (
                page_number < total_pages
                and len(links) != 10
            ):

                raise RuntimeError(
                    f"Strona {page_number}: "
                    f"oczekiwano 10 wyników, "
                    f"otrzymano {len(links)}."
                )

            # ------------------------------------------------
            # Добавляем ID в SQLite.
            # ------------------------------------------------

            new_count, existing_count = (
                add_documents(
                    links
                )
            )

            total_new += new_count
            total_existing += (
                existing_count
            )

            print(
                "Nowych:",
                new_count
            )

            print(
                "Już było:",
                existing_count
            )

            # =================================================
            # CHECKPOINT
            #
            # Очень важная строка.
            #
            # Сохраняем следующую страницу ТОЛЬКО
            # после успешной обработки текущей.
            # =================================================

            new_next_page = (
                page_number + 1
            )

            update_search_next_page(
                job_id,
                new_next_page
            )

            print(
                "Checkpoint zapisany."
            )

            print(
                "Następna strona:",
                new_next_page
            )

        except Exception as error:

            mark_search_job_error(
                job_id,
                str(error)
            )

            print(
                "\n!!! BŁĄD STRONY !!!"
            )

            print(
                type(error).__name__,
                error
            )

            print(
                "Checkpoint NIE został przesunięty."
            )

            print(
                "Po kolejnym uruchomieniu "
                "program spróbuje tej strony ponownie."
            )

            return

        # ----------------------------------------------------
        # Пауза.
        # ----------------------------------------------------

        if (
            page_number
            < last_page_this_run
        ):

            print(
                f"Czekam "
                f"{PAGE_DELAY} sek..."
            )

            time.sleep(
                PAGE_DELAY
            )

    # ========================================================
    # 8. Проверяем, закончился ли весь диапазон.
    # ========================================================

    final_next_page = (
        last_page_this_run + 1
    )

    if final_next_page > total_pages:

        mark_search_job_done(
            job_id
        )

        final_status = "done"

    else:

        final_status = "running"

    # ========================================================
    # 9. ИТОГ
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
        "Nowych ID:",
        total_new
    )

    print(
        "Już istniejących:",
        total_existing
    )

    print(
        "Wszystkich w documents:",
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
        "Status search job:",
        final_status
    )

    print(
        "\nSearch jobs:"
    )

    for row in show_search_jobs():

        print(
            row
        )


if __name__ == "__main__":
    main()
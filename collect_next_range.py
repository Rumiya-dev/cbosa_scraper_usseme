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
    get_next_search_job,

    update_search_total_pages,
    update_search_next_page,

    mark_search_job_done,
    mark_search_job_error,

    show_search_jobs,
)


# ============================================================
# USTAWIENIA
# ============================================================

# Пока специально только 3 страницы за запуск.
#
# Это нужно для проверки checkpoint.
PAGES_PER_RUN = 3


# Пауза между страницами результатов.
PAGE_DELAY = 5


# ============================================================
# PRZYWRACANIE WYSZUKIWANIA
# ============================================================

def restore_search_context(
    date_from,
    date_to
):
    """
    Tworzy nową sesję HTTP i ponownie wykonuje
    wyszukiwanie dla konkretnego zakresu dat.

    Jest potrzebne, jeśli CBOSA utraci
    kontekst wyszukiwania.
    """

    print(
        "\n========================================"
    )

    print(
        "PRZYWRACAM KONTEKST WYSZUKIWANIA"
    )

    print(
        "========================================"
    )

    print(
        "Zakres:",
        date_from,
        "->",
        date_to
    )

    # Закрываем старую HTTP-сессию
    # и создаём новую.
    reset_session()

    # Заходим на CBOSA,
    # чтобы получить cookies.
    open_cbosa()

    time.sleep(2)

    # Снова выполняем поиск.
    first_page_html = search_documents(
        date_from,
        date_to
    )

    # Проверяем, что получили настоящую выдачу.
    info = extract_search_info(
        first_page_html
    )

    print(
        "Kontekst przywrócony."
    )

    print(
        "Wyników:",
        info["total_documents"]
    )

    print(
        "Stron:",
        info["total_pages"]
    )

    return first_page_html


# ============================================================
# POPRAWNA STRONA WYNIKÓW
# ============================================================

def get_valid_result_page(
    page_number,
    first_page_html,
    date_from,
    date_to,
):
    """
    Pobiera stronę wyników i sprawdza,
    czy CBOSA rzeczywiście zwróciła
    żądany numer strony.
    """

    # ========================================================
    # STRONA 1
    # ========================================================

    if page_number == 1:

        html = first_page_html

    # ========================================================
    # STRONA 2, 3, 4...
    # ========================================================

    else:

        html = download_result_page(
            page_number
        )

    # ========================================================
    # WALIDACJA
    # ========================================================

    try:

        info = extract_search_info(
            html
        )

        received_page = (
            info["current_page"]
        )

    except Exception:

        received_page = None

    # Сервер вернул правильную страницу.
    if received_page == page_number:

        return html

    # ========================================================
    # ПРОБЛЕМА С СЕССИЕЙ
    # ========================================================

    print(
        "\nUWAGA!"
    )

    print(
        "CBOSA nie zwróciła "
        "oczekiwanej strony."
    )

    print(
        "Oczekiwano:",
        page_number
    )

    print(
        "Otrzymano:",
        received_page
    )

    print(
        "Odtwarzam wyszukiwanie..."
    )

    new_first_page = restore_search_context(
        date_from,
        date_to
    )

    # После восстановления повторяем запрос.

    if page_number == 1:

        html = new_first_page

    else:

        html = download_result_page(
            page_number
        )

    # ========================================================
    # ВТОРАЯ ПРОВЕРКА
    # ========================================================

    info = extract_search_info(
        html
    )

    received_page = (
        info["current_page"]
    )

    if received_page != page_number:

        raise RuntimeError(
            f"Nie udało się pobrać "
            f"strony {page_number}. "
            f"CBOSA zwróciła "
            f"stronę {received_page}."
        )

    return html


# ============================================================
# STATYSTYKI
# ============================================================

def print_statistics():

    print(
        "\n========================================"
    )

    print(
        "SQLITE"
    )

    print(
        "========================================"
    )

    print(
        "Wszystkich dokumentów:",
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


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "========================================"
    )

    print(
        "CBOSA - AUTOMATYCZNY COLLECTOR"
    )

    print(
        "========================================"
    )

    # ========================================================
    # 1. БАЗА
    # ========================================================

    create_database()

    create_search_jobs_table()

    print_statistics()

    # ========================================================
    # 2. ВЫБИРАЕМ СЛЕДУЮЩИЙ ДИАПАЗОН
    # ========================================================

    job = get_next_search_job()

    if job is None:

        print(
            "\nBrak search jobs do wykonania."
        )

        return

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
        "WYBRANY SEARCH JOB"
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
        "Next page:",
        next_page
    )

    print(
        "Saved total pages:",
        saved_total_pages
    )

    print(
        "Status:",
        status
    )

    # ========================================================
    # 3. ОТКРЫВАЕМ CBOSA
    # ========================================================

    try:

        print(
            "\nOtwieram CBOSA..."
        )

        open_cbosa()

        time.sleep(2)

        # ----------------------------------------------------
        # Каждый новый запуск повторяет POST search.
        #
        # Это нужно, чтобы сервер снова знал,
        # какой диапазон дат мы просматриваем.
        # ----------------------------------------------------

        print(
            "\nWykonuję wyszukiwanie:"
        )

        print(
            date_from,
            "->",
            date_to
        )

        first_page_html = search_documents(
            date_from,
            date_to
        )

        search_info = extract_search_info(
            first_page_html
        )

    except Exception as error:

        mark_search_job_error(
            job_id,
            str(error)
        )

        print(
            "\n!!! BŁĄD URUCHOMIENIA SEARCH JOB !!!"
        )

        print(
            type(error).__name__,
            error
        )

        return

    # ========================================================
    # 4. ИНФОРМАЦИЯ О ВЫДАЧЕ
    # ========================================================

    total_documents = (
        search_info["total_documents"]
    )

    total_pages = (
        search_info["total_pages"]
    )

    print(
        "\nZnalezionych orzeczeń:",
        total_documents
    )

    print(
        "Liczba stron:",
        total_pages
    )

    # Записываем актуальное количество страниц.
    update_search_total_pages(
        job_id,
        total_pages
    )

    # ========================================================
    # 5. МОЖЕТ БЫТЬ ДИАПАЗОН УЖЕ ЗАКОНЧЕН
    # ========================================================

    if next_page > total_pages:

        mark_search_job_done(
            job_id
        )

        print(
            "\nTen zakres jest już zakończony."
        )

        return

    # ========================================================
    # 6. СКОЛЬКО СТРАНИЦ СДЕЛАЕМ СЕЙЧАС
    # ========================================================

    last_page_this_run = min(
        next_page
        + PAGES_PER_RUN
        - 1,

        total_pages
    )

    print(
        "\n========================================"
    )

    print(
        "TEN RUN"
    )

    print(
        "========================================"
    )

    print(
        "Od strony:",
        next_page
    )

    print(
        "Do strony:",
        last_page_this_run
    )

    total_new = 0
    total_existing = 0
    pages_completed = 0

    # ========================================================
    # 7. СТРАНИЦЫ
    # ========================================================

    for page_number in range(
        next_page,
        last_page_this_run + 1
    ):

        print(
            "\n========================================"
        )

        print(
            f"STRONA "
            f"{page_number}/{total_pages}"
        )

        print(
            "========================================"
        )

        try:

            # ------------------------------------------------
            # Скачать и проверить страницу.
            # ------------------------------------------------

            html = get_valid_result_page(
                page_number,
                first_page_html,
                date_from,
                date_to,
            )

            # ------------------------------------------------
            # Найти основные doc links.
            # ------------------------------------------------

            links = extract_document_links(
                html
            )

            print(
                "Głównych linków:",
                len(links)
            )

            # ------------------------------------------------
            # Проверка.
            #
            # На любой НЕ последней странице
            # ожидаем ровно 10 основных результатов.
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
            # SQLite.
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

            pages_completed += 1

            print(
                "Nowych ID:",
                new_count
            )

            print(
                "Już istniało:",
                existing_count
            )

            # =================================================
            # CHECKPOINT
            # =================================================

            new_next_page = (
                page_number + 1
            )

            update_search_next_page(
                job_id,
                new_next_page
            )

            print(
                "Checkpoint:"
            )

            print(
                "next_page =",
                new_next_page
            )

        except Exception as error:

            # =================================================
            # НЕ СДВИГАЕМ CHECKPOINT
            # =================================================

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
                "Checkpoint pozostaje "
                "na tej stronie."
            )

            print(
                "Następny запуск spróbuje ponownie."
            )

            return

        # ====================================================
        # ПАУЗА
        # ====================================================

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
    # 8. ЗАКОНЧИЛИ ЛИ ВЕСЬ МЕСЯЦ
    # ========================================================

    next_after_run = (
        last_page_this_run + 1
    )

    if next_after_run > total_pages:

        mark_search_job_done(
            job_id
        )

        job_finished = True

    else:

        job_finished = False

    # ========================================================
    # 9. РЕЗУЛЬТАТ
    # ========================================================

    print(
        "\n========================================"
    )

    print(
        "PODSUMOWANIE RUN"
    )

    print(
        "========================================"
    )

    print(
        "Job:",
        job_id
    )

    print(
        "Zakres:",
        date_from,
        "->",
        date_to
    )

    print(
        "Przetworzonych stron:",
        pages_completed
    )

    print(
        "Nowych ID:",
        total_new
    )

    print(
        "Już istniejących:",
        total_existing
    )

    if job_finished:

        print(
            "SEARCH JOB: DONE"
        )

    else:

        print(
            "SEARCH JOB: RUNNING"
        )

        print(
            "Następny start od strony:",
            next_after_run
        )

    print_statistics()

    print(
        "\n========================================"
    )

    print(
        "SEARCH JOBS"
    )

    print(
        "========================================"
    )

    for row in show_search_jobs():

        print(
            row
        )


if __name__ == "__main__":
    main()
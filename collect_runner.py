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
# USTAWIENIA RUNNERA
# ============================================================

# Максимум страниц за ОДИН запуск программы.
#
# Пока ставим 20.
#
# Позже после тестирования сможем изменить.
MAX_PAGES_PER_RUN = 20


# Пауза между страницами результатов.
PAGE_DELAY = 5


# Небольшая пауза при переходе
# с одного диапазона дат на другой.
JOB_DELAY = 10


# ============================================================
# PRZYWRACANIE KONTEKSTU SEARCH
# ============================================================

def restore_search_context(
    date_from,
    date_to
):
    """
    Tworzy nową sesję HTTP
    i ponownie wykonuje wyszukiwanie
    dla konkretnego zakresu dat.
    """

    print(
        "\n========================================"
    )
    print(
        "PRZYWRACAM KONTEKST SEARCH"
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

    reset_session()

    open_cbosa()

    time.sleep(2)

    first_page_html = search_documents(
        date_from,
        date_to
    )

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
# POBIERANIE POPRAWNEJ STRONY
# ============================================================

def get_valid_result_page(
    page_number,
    first_page_html,
    date_from,
    date_to
):
    """
    Pobiera konkretną stronę wyników
    i sprawdza jej numer.
    """

    # --------------------------------------------------------
    # PAGE 1
    # --------------------------------------------------------

    if page_number == 1:

        html = first_page_html

    else:

        html = download_result_page(
            page_number
        )

    # --------------------------------------------------------
    # Проверяем страницу.
    # --------------------------------------------------------

    try:

        info = extract_search_info(
            html
        )

        received_page = (
            info["current_page"]
        )

    except Exception:

        received_page = None

    # Всё нормально.
    if received_page == page_number:

        return html

    # --------------------------------------------------------
    # Контекст поиска потерялся.
    # --------------------------------------------------------

    print(
        "\nUWAGA:"
    )

    print(
        "Oczekiwano strony:",
        page_number
    )

    print(
        "Otrzymano:",
        received_page
    )

    print(
        "Przywracam search..."
    )

    new_first_page = restore_search_context(
        date_from,
        date_to
    )

    if page_number == 1:

        html = new_first_page

    else:

        html = download_result_page(
            page_number
        )

    # --------------------------------------------------------
    # Вторая проверка.
    # --------------------------------------------------------

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
            f"Otrzymano {received_page}."
        )

    return html


# ============================================================
# STATYSTYKI SQLITE
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
        "Wszystkich:",
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
# OTWARCIE SEARCH JOB
# ============================================================

def open_search_job(job):
    """
    Otwiera jeden search job.

    Wykonuje ponownie POST /search,
    ponieważ CBOSA musi znać aktywny
    zakres wyszukiwania.
    """

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
        "SEARCH JOB"
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
        "Checkpoint:",
        next_page
    )

    print(
        "Saved total pages:",
        saved_total_pages
    )

    # --------------------------------------------------------
    # Новая HTTP-сессия для нового диапазона.
    # --------------------------------------------------------

    reset_session()

    open_cbosa()

    time.sleep(2)

    # --------------------------------------------------------
    # Восстанавливаем поиск.
    # --------------------------------------------------------

    first_page_html = search_documents(
        date_from,
        date_to
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
        "Orzeczeń:",
        total_documents
    )

    print(
        "Stron:",
        total_pages
    )

    return {
        "job_id":
            job_id,

        "date_from":
            date_from,

        "date_to":
            date_to,

        "next_page":
            next_page,

        "total_pages":
            total_pages,

        "first_page_html":
            first_page_html,
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "========================================"
    )
    print(
        "CBOSA - COLLECTOR RUNNER"
    )
    print(
        "========================================"
    )

    create_database()

    create_search_jobs_table()

    print_statistics()

    # --------------------------------------------------------
    # Сколько страниц обработано
    # именно во время этого запуска.
    # --------------------------------------------------------

    pages_this_run = 0

    total_new_ids = 0

    total_existing_ids = 0

    jobs_finished = 0

    # ========================================================
    # ГЛАВНЫЙ ЦИКЛ
    # ========================================================

    while pages_this_run < MAX_PAGES_PER_RUN:

        # ----------------------------------------------------
        # 1. Берём следующий незаконченный диапазон.
        # ----------------------------------------------------

        job = get_next_search_job()

        if job is None:

            print(
                "\nBrak kolejnych search jobs."
            )

            break

        # ----------------------------------------------------
        # 2. Открываем search job.
        # ----------------------------------------------------

        try:

            context = open_search_job(
                job
            )

        except Exception as error:

            job_id = job[0]

            mark_search_job_error(
                job_id,
                str(error)
            )

            print(
                "\n!!! BŁĄD SEARCH JOB !!!"
            )

            print(
                type(error).__name__,
                error
            )

            print(
                "Runner kończy ten запуск."
            )

            break

        job_id = context[
            "job_id"
        ]

        date_from = context[
            "date_from"
        ]

        date_to = context[
            "date_to"
        ]

        page_number = context[
            "next_page"
        ]

        total_pages = context[
            "total_pages"
        ]

        first_page_html = context[
            "first_page_html"
        ]

        # ----------------------------------------------------
        # Возможно, этот job уже фактически закончен.
        # ----------------------------------------------------

        if page_number > total_pages:

            mark_search_job_done(
                job_id
            )

            jobs_finished += 1

            print(
                "SEARCH JOB już zakończony."
            )

            continue

        # ====================================================
        # ЦИКЛ СТРАНИЦ ТЕКУЩЕГО JOB
        # ====================================================

        while (
            page_number <= total_pages
            and
            pages_this_run < MAX_PAGES_PER_RUN
        ):

            print(
                "\n========================================"
            )

            print(
                f"STRONA "
                f"{page_number}/"
                f"{total_pages}"
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

            try:

                # --------------------------------------------
                # Скачать страницу.
                # --------------------------------------------

                html = get_valid_result_page(
                    page_number,
                    first_page_html,
                    date_from,
                    date_to,
                )

                # --------------------------------------------
                # Извлечь основные doc links.
                # --------------------------------------------

                links = (
                    extract_document_links(
                        html
                    )
                )

                print(
                    "Głównych linków:",
                    len(links)
                )

                # --------------------------------------------
                # Проверка количества.
                # --------------------------------------------

                if (
                    page_number < total_pages
                    and len(links) != 10
                ):

                    raise RuntimeError(
                        f"Strona "
                        f"{page_number}: "
                        f"oczekiwano 10, "
                        f"otrzymano "
                        f"{len(links)}."
                    )

                # --------------------------------------------
                # SQLite.
                # --------------------------------------------

                (
                    new_count,
                    existing_count
                ) = add_documents(
                    links
                )

                total_new_ids += (
                    new_count
                )

                total_existing_ids += (
                    existing_count
                )

                print(
                    "Nowych ID:",
                    new_count
                )

                print(
                    "Już było:",
                    existing_count
                )

                # ============================================
                # CHECKPOINT
                # ============================================

                page_number += 1

                update_search_next_page(
                    job_id,
                    page_number
                )

                pages_this_run += 1

                print(
                    "Checkpoint:"
                )

                print(
                    "next_page =",
                    page_number
                )

                print(
                    "Pages this run:",
                    pages_this_run,
                    "/",
                    MAX_PAGES_PER_RUN
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
                    "Checkpoint NIE przesunięty."
                )

                print(
                    "Runner kończy ten запуск."
                )

                print_statistics()

                return

            # -----------------------------------------------
            # Пауза между страницами.
            # -----------------------------------------------

            if (
                page_number <= total_pages
                and
                pages_this_run < MAX_PAGES_PER_RUN
            ):

                print(
                    f"Czekam "
                    f"{PAGE_DELAY} sek..."
                )

                time.sleep(
                    PAGE_DELAY
                )

        # ====================================================
        # JOB ЗАКОНЧЕН
        # ====================================================

        if page_number > total_pages:

            mark_search_job_done(
                job_id
            )

            jobs_finished += 1

            print(
                "\n========================================"
            )

            print(
                "SEARCH JOB DONE"
            )

            print(
                "========================================"
            )

            print(
                date_from,
                "->",
                date_to
            )

            # Если есть ещё бюджет страниц,
            # можем перейти к следующему диапазону.
            if pages_this_run < MAX_PAGES_PER_RUN:

                print(
                    f"Czekam "
                    f"{JOB_DELAY} sek "
                    "przed następnym zakresem..."
                )

                time.sleep(
                    JOB_DELAY
                )

    # ========================================================
    # КОНЕЦ RUN
    # ========================================================

    print(
        "\n========================================"
    )

    print(
        "KONIEC RUNNERA"
    )

    print(
        "========================================"
    )

    print(
        "Przetworzonych stron:",
        pages_this_run
    )

    print(
        "Nowych ID:",
        total_new_ids
    )

    print(
        "Już istniejących ID:",
        total_existing_ids
    )

    print(
        "Zakończonych search jobs:",
        jobs_finished
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
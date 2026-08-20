import os
import time
import statistics

import requests

from cbosa_client import (
    BASE_URL,
    session,
    open_cbosa,
)

from database import (
    create_database,
    get_documents_to_process,
    save_document_result,
    mark_failed,
    count_documents,
    count_by_status,
)

from parse_document import parse_document


# ============================================================
# USTAWIENIA
# ============================================================

BENCHMARK_LIMIT = 15

MAX_HTTP_RETRIES = 5

DOCUMENT_DELAY = 6

MAX_DOCUMENT_ATTEMPTS = 3

SAVE_RAW_HTML = True

RAW_HTML_DIR = "raw_html"

DOC_REFERER = (
    f"{BASE_URL}/pl/cbo/search"
)


# ============================================================
# HTTP Z POMIAREM
# ============================================================

def download_with_metrics(url):
    """
    Pobiera jeden dokument i jednocześnie mierzy:

    - ile wykonano prób HTTP
    - ile sekund trwało pobranie wraz z retry

    Zwraca:

        html_bytes
        attempts
        elapsed_seconds
    """

    start_time = time.perf_counter()

    last_error = None

    for attempt in range(
        1,
        MAX_HTTP_RETRIES + 1
    ):

        print(
            f"HTTP próba "
            f"{attempt}/{MAX_HTTP_RETRIES}"
        )

        try:

            response = session.get(
                url,
                headers={
                    "Referer":
                        DOC_REFERER,
                },
                timeout=60,
            )

            print(
                "Status:",
                response.status_code
            )

            if response.status_code == 200:

                elapsed = (
                    time.perf_counter()
                    - start_time
                )

                return (
                    response.content,
                    attempt,
                    elapsed,
                )

            last_error = RuntimeError(
                f"HTTP {response.status_code}"
            )

        except requests.RequestException as error:

            last_error = error

            print(
                "Błąd:",
                type(error).__name__,
                error
            )

        if attempt < MAX_HTTP_RETRIES:

            wait_time = (
                5 * (2 ** (attempt - 1))
            )

            print(
                f"Czekam {wait_time} sek..."
            )

            time.sleep(
                wait_time
            )

    elapsed = (
        time.perf_counter()
        - start_time
    )

    raise RuntimeError(
        f"Nie udało się pobrać dokumentu "
        f"po {MAX_HTTP_RETRIES} próbach. "
        f"Czas: {elapsed:.2f}s. "
        f"Ostatni błąd: {last_error}"
    )


# ============================================================
# RAW HTML
# ============================================================

def save_raw_html(
    doc_id,
    html_bytes
):

    os.makedirs(
        RAW_HTML_DIR,
        exist_ok=True
    )

    path = os.path.join(
        RAW_HTML_DIR,
        f"{doc_id}.html"
    )

    with open(
        path,
        "wb"
    ) as file:

        file.write(
            html_bytes
        )

    return path


# ============================================================
# WALIDACJA
# ============================================================

def validate_document(parsed_data):

    required = [
        "sygnatura",
        "data_orzeczenia",
        "sad",
        "sentencja_html",
    ]

    missing = []

    for field in required:

        if not parsed_data.get(field):

            missing.append(field)

    if missing:

        raise RuntimeError(
            "Brak wymaganych pól: "
            + ", ".join(missing)
        )


# ============================================================
# STATYSTYKI
# ============================================================

def print_database_stats():

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
# MAIN
# ============================================================

def main():

    print(
        "========================================"
    )

    print(
        "CBOSA BENCHMARK"
    )

    print(
        "========================================"
    )

    create_database()

    print_database_stats()

    # --------------------------------------------------------
    # Берём до 15 документов.
    # --------------------------------------------------------

    documents = get_documents_to_process(
        limit=BENCHMARK_LIMIT,
        max_attempts=MAX_DOCUMENT_ATTEMPTS,
    )

    print(
        "\nDokumentów do benchmarku:",
        len(documents)
    )

    if not documents:

        print(
            "Brak dokumentów do przetworzenia."
        )

        return

    # --------------------------------------------------------
    # Открываем CBOSA и получаем cookies.
    # --------------------------------------------------------

    print(
        "\nOtwieram CBOSA..."
    )

    open_cbosa()

    time.sleep(2)

    # --------------------------------------------------------
    # Метрики.
    # --------------------------------------------------------

    download_times = []

    html_sizes = []

    http_attempts_list = []

    no_uzasadnienie = 0

    successful = 0

    failed = 0

    benchmark_start = (
        time.perf_counter()
    )

    # --------------------------------------------------------
    # Обработка.
    # --------------------------------------------------------

    for index, row in enumerate(
        documents,
        start=1
    ):

        (
            doc_id,
            url,
            previous_status,
            previous_attempts,
        ) = row

        print(
            "\n========================================"
        )

        print(
            f"DOKUMENT "
            f"{index}/{len(documents)}"
        )

        print(
            "========================================"
        )

        print(
            "ID:",
            doc_id
        )

        try:

            # ================================================
            # 1. DOWNLOAD
            # ================================================

            html_bytes, http_attempts, download_time = (
                download_with_metrics(
                    url
                )
            )

            size_bytes = len(
                html_bytes
            )

            print(
                f"Czas downloadu: "
                f"{download_time:.2f} s"
            )

            print(
                "HTTP attempts:",
                http_attempts
            )

            print(
                "HTML bytes:",
                size_bytes
            )

            # ================================================
            # 2. RAW HTML
            # ================================================

            if SAVE_RAW_HTML:

                save_raw_html(
                    doc_id,
                    html_bytes
                )

            # ================================================
            # 3. PARSE
            # ================================================

            html_text = html_bytes.decode(
                "utf-8",
                errors="replace"
            )

            parsed_data = parse_document(
                html_text
            )

            validate_document(
                parsed_data
            )

            # ================================================
            # 4. Проверяем uzasadnienie
            # ================================================

            if not parsed_data.get(
                "uzasadnienie_html"
            ):

                no_uzasadnienie += 1

            # ================================================
            # 5. SAVE SQLITE
            # ================================================

            result = {
                "doc_id":
                    doc_id,

                "url":
                    url,

                **parsed_data,
            }

            save_document_result(
                doc_id,
                result
            )

            # ================================================
            # 6. Метрики только успешного документа
            # ================================================

            download_times.append(
                download_time
            )

            html_sizes.append(
                size_bytes
            )

            http_attempts_list.append(
                http_attempts
            )

            successful += 1

            print(
                "STATUS: DONE"
            )

        except Exception as error:

            failed += 1

            print(
                "\n!!! BŁĄD !!!"
            )

            print(
                type(error).__name__,
                error
            )

            mark_failed(
                doc_id,
                str(error)
            )

            print(
                "STATUS: FAILED"
            )

        # ----------------------------------------------------
        # Пауза между документами.
        # ----------------------------------------------------

        if index < len(documents):

            print(
                f"Czekam "
                f"{DOCUMENT_DELAY} sek..."
            )

            time.sleep(
                DOCUMENT_DELAY
            )

    # --------------------------------------------------------
    # Полное wall-clock время.
    # --------------------------------------------------------

    total_elapsed = (
        time.perf_counter()
        - benchmark_start
    )

    # --------------------------------------------------------
    # RESULT
    # --------------------------------------------------------

    print(
        "\n========================================"
    )

    print(
        "WYNIKI BENCHMARKU"
    )

    print(
        "========================================"
    )

    print(
        "Dokumentów:",
        len(documents)
    )

    print(
        "OK:",
        successful
    )

    print(
        "Błędy:",
        failed
    )

    print(
        "Bez uzasadnienia:",
        no_uzasadnienie
    )

    print(
        f"Cały test: "
        f"{total_elapsed:.2f} s"
    )

    if download_times:

        print(
            "\n--- CZAS DOWNLOADU ---"
        )

        print(
            f"Średnia: "
            f"{statistics.mean(download_times):.2f} s"
        )

        print(
            f"Mediana: "
            f"{statistics.median(download_times):.2f} s"
        )

        print(
            f"Minimum: "
            f"{min(download_times):.2f} s"
        )

        print(
            f"Maksimum: "
            f"{max(download_times):.2f} s"
        )

    if html_sizes:

        average_size = (
            statistics.mean(
                html_sizes
            )
        )

        print(
            "\n--- HTML ---"
        )

        print(
            f"Średni rozmiar: "
            f"{average_size:.0f} bytes"
        )

        print(
            f"Minimum: "
            f"{min(html_sizes)} bytes"
        )

        print(
            f"Maksimum: "
            f"{max(html_sizes)} bytes"
        )

    if http_attempts_list:

        total_http_attempts = sum(
            http_attempts_list
        )

        retries = (
            total_http_attempts
            - len(http_attempts_list)
        )

        documents_with_retry = sum(
            1
            for attempts
            in http_attempts_list
            if attempts > 1
        )

        print(
            "\n--- HTTP ---"
        )

        print(
            "Wszystkich prób HTTP:",
            total_http_attempts
        )

        print(
            "Dodatkowych retry:",
            retries
        )

        print(
            "Dokumentów wymagających retry:",
            documents_with_retry
        )

        print(
            "Średnia liczba prób / dokument:",
            round(
                statistics.mean(
                    http_attempts_list
                ),
                2
            )
        )

    print_database_stats()


if __name__ == "__main__":
    main()
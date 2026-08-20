import os
import time
import statistics

from cbosa_client import (
    BASE_URL,
    open_cbosa,
    request_with_retry,
)

from database import (
    create_database,
    get_documents_to_process,
    save_document_result,
    mark_failed,

    count_documents,
    count_by_status,
)

from parse_document import (
    parse_document,
)


# ============================================================
# USTAWIENIA
# ============================================================

# Пока тестируем 20 документов за один запуск.
MAX_DOCUMENTS_PER_RUN = 100


# После 3 полностью неудачных запусков
# конкретный документ перестаём автоматически брать.
MAX_DOCUMENT_ATTEMPTS = 3


# Осторожная пауза между документами.
#
# Пока оставляем 6 секунд.
DOCUMENT_DELAY = 3


# Если parser сломается на конкретном HTML,
# сохраним этот HTML для отладки.
FAILED_HTML_DIR = "failed_html"


DOC_REFERER = (
    f"{BASE_URL}/pl/cbo/search"
)


# ============================================================
# DOWNLOAD
# ============================================================

def download_document(url):
    """
    Pobiera pojedyncze orzeczenie.

    request_with_retry() zawiera już:
    - krótkie retry,
    - exponential backoff,
    - recovery po dłuższej awarii.
    """

    response = request_with_retry(
        "GET",
        url,

        headers={
            "Referer":
                DOC_REFERER,
        },
    )

    return response.content


# ============================================================
# ZAPIS HTML TYLKO PRZY PROBLEMIE
# ============================================================

def save_failed_html(
    doc_id,
    html_bytes
):
    """
    Jeśli dokument został pobrany,
    ale parser / walidacja się nie udały,
    zapisujemy HTML do debugowania.
    """

    os.makedirs(
        FAILED_HTML_DIR,
        exist_ok=True
    )

    path = os.path.join(
        FAILED_HTML_DIR,
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

def validate_document(
    parsed_data
):
    """
    Sprawdzamy podstawowe pola.

    Uzasadnienie NIE jest obowiązkowe,
    ponieważ już wiemy, że nie każde
    orzeczenie je posiada.
    """

    required_fields = [
        "sygnatura",
        "data_orzeczenia",
        "sad",
        "sentencja_html",
    ]

    missing = []

    for field in required_fields:

        value = parsed_data.get(
            field
        )

        if not value:

            missing.append(
                field
            )

    if missing:

        raise RuntimeError(
            "Brak wymaganych pól: "
            + ", ".join(missing)
        )


# ============================================================
# STATYSTYKI BAZY
# ============================================================

def print_database_statistics():

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
        "CBOSA - PROCESSOR RUNNER"
    )

    print(
        "========================================"
    )

    # ========================================================
    # 1. БАЗА
    # ========================================================

    create_database()

    print_database_statistics()

    # ========================================================
    # 2. ПОЛУЧАЕМ ОЧЕРЕДЬ
    # ========================================================

    documents = get_documents_to_process(
        limit=MAX_DOCUMENTS_PER_RUN,
        max_attempts=MAX_DOCUMENT_ATTEMPTS,
    )

    print(
        "\n========================================"
    )

    print(
        "KOLEJKA"
    )

    print(
        "========================================"
    )

    print(
        "Dokumentów do pracy:",
        len(documents)
    )

    if not documents:

        print(
            "Brak dokumentów do przetworzenia."
        )

        return

    # ========================================================
    # 3. ОТКРЫВАЕМ CBOSA
    # ========================================================

    print(
        "\nOtwieram CBOSA..."
    )

    try:

        open_cbosa()

    except Exception as error:

        print(
            "\nNie udało się otworzyć CBOSA."
        )

        print(
            type(error).__name__,
            error
        )

        # Важно:
        # документы НЕ переводим в failed,
        # потому что мы даже не начали
        # обрабатывать конкретный документ.
        return

    time.sleep(2)

    # ========================================================
    # 4. МЕТРИКИ
    # ========================================================

    successful = 0
    failed = 0

    no_uzasadnienie = 0

    processing_times = []

    html_sizes = []

    run_start = time.perf_counter()

    # ========================================================
    # 5. ОБРАБОТКА
    # ========================================================

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

        print(
            "Status wcześniej:",
            previous_status
        )

        print(
            "Nieudane runy wcześniej:",
            previous_attempts
        )

        document_start = (
            time.perf_counter()
        )

        html_bytes = None

        try:

            # =================================================
            # A. DOWNLOAD
            # =================================================

            print(
                "\n1. Download..."
            )

            download_start = (
                time.perf_counter()
            )

            html_bytes = download_document(
                url
            )

            download_time = (
                time.perf_counter()
                - download_start
            )

            html_size = len(
                html_bytes
            )

            print(
                f"Download: "
                f"{download_time:.2f} s"
            )

            print(
                "HTML:",
                html_size,
                "bytes"
            )

            # =================================================
            # B. BYTES -> TEXT
            # =================================================

            html_text = html_bytes.decode(
                "utf-8",
                errors="replace"
            )

            # =================================================
            # C. PARSER
            # =================================================

            print(
                "\n2. Parse..."
            )

            parsed_data = parse_document(
                html_text
            )

            print(
                "Sygnatura:",
                parsed_data.get(
                    "sygnatura"
                )
            )

            # =================================================
            # D. VALIDATION
            # =================================================

            print(
                "\n3. Walidacja..."
            )

            validate_document(
                parsed_data
            )

            print(
                "Walidacja OK."
            )

            # =================================================
            # E. UZASADNIENIE
            # =================================================

            if not parsed_data.get(
                "uzasadnienie_html"
            ):

                no_uzasadnienie += 1

                print(
                    "Uzasadnienie: BRAK"
                )

            else:

                print(
                    "Uzasadnienie: OK"
                )

            # =================================================
            # F. RESULT
            # =================================================

            result = {
                "doc_id":
                    doc_id,

                "url":
                    url,

                **parsed_data,
            }

            # =================================================
            # G. SQLITE
            # =================================================

            print(
                "\n4. SQLite..."
            )

            save_document_result(
                doc_id,
                result
            )

            document_time = (
                time.perf_counter()
                - document_start
            )

            processing_times.append(
                document_time
            )

            html_sizes.append(
                html_size
            )

            successful += 1

            print(
                "STATUS: DONE"
            )

            print(
                f"Czas dokumentu: "
                f"{document_time:.2f} s"
            )

        except Exception as error:

            failed += 1

            print(
                "\n!!! BŁĄD DOKUMENTU !!!"
            )

            print(
                type(error).__name__,
                error
            )

            # -------------------------------------------------
            # Если HTML получили, но parser или validation
            # сломались, сохраняем страницу.
            # -------------------------------------------------

            if html_bytes is not None:

                try:

                    failed_path = save_failed_html(
                        doc_id,
                        html_bytes
                    )

                    print(
                        "HTML błędu zapisany:",
                        failed_path
                    )

                except Exception as save_error:

                    print(
                        "Nie udało się zapisać "
                        "HTML błędu:",
                        save_error
                    )

            # -------------------------------------------------
            # Ставим failed.
            # -------------------------------------------------

            mark_failed(
                doc_id,
                str(error)
            )

            print(
                "STATUS: FAILED"
            )

        # ====================================================
        # ПАУЗА
        # ====================================================

        if index < len(documents):

            print(
                f"\nCzekam "
                f"{DOCUMENT_DELAY} sek..."
            )

            time.sleep(
                DOCUMENT_DELAY
            )

    # ========================================================
    # 6. ОБЩЕЕ ВРЕМЯ
    # ========================================================

    total_run_time = (
        time.perf_counter()
        - run_start
    )

    # ========================================================
    # 7. РЕЗУЛЬТАТЫ
    # ========================================================

    print(
        "\n========================================"
    )

    print(
        "KONIEC PROCESSOR RUNNER"
    )

    print(
        "========================================"
    )

    print(
        "Dokumentów w batchu:",
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
        f"Cały run: "
        f"{total_run_time:.2f} s"
    )

    # ========================================================
    # 8. СТАТИСТИКА ВРЕМЕНИ
    # ========================================================

    if processing_times:

        print(
            "\n--- CZAS DOKUMENTU ---"
        )

        print(
            f"Średnia: "
            f"{statistics.mean(processing_times):.2f} s"
        )

        print(
            f"Mediana: "
            f"{statistics.median(processing_times):.2f} s"
        )

        print(
            f"Minimum: "
            f"{min(processing_times):.2f} s"
        )

        print(
            f"Maksimum: "
            f"{max(processing_times):.2f} s"
        )

    # ========================================================
    # 9. HTML SIZE
    # ========================================================

    if html_sizes:

        print(
            "\n--- HTML ---"
        )

        print(
            f"Średnia: "
            f"{statistics.mean(html_sizes):.0f} bytes"
        )

        print(
            "Minimum:",
            min(html_sizes),
            "bytes"
        )

        print(
            "Maksimum:",
            max(html_sizes),
            "bytes"
        )

    # ========================================================
    # 10. SQLITE ПОСЛЕ RUN
    # ========================================================

    print_database_statistics()


if __name__ == "__main__":
    main()
import os
import time

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

PROCESS_LIMIT = 3

MAX_DOCUMENT_ATTEMPTS = 3

DOCUMENT_DELAY = 6

RAW_HTML_DIR = "raw_html"

SAVE_RAW_HTML = True

DOC_REFERER = (
    f"{BASE_URL}/pl/cbo/search"
)


# ============================================================
# DOWNLOAD
# ============================================================

def download_document(url):

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
# VALIDATION
# ============================================================

def validate_document(
    parsed_data
):
    """
    Sprawdza najważniejsze pola.

    Nie chcemy zapisywać jako DONE
    strony błędu albo pustego HTML.
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
# STATYSTYKI
# ============================================================

def print_statistics():

    print(
        "\n========================================"
    )

    print(
        "STATYSTYKI"
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
        "CBOSA PROCESSOR V2"
    )

    print(
        "========================================"
    )

    # --------------------------------------------------------
    # 1. База + миграция
    # --------------------------------------------------------

    create_database()

    print_statistics()

    # --------------------------------------------------------
    # 2. Получаем очередь
    # --------------------------------------------------------

    documents = get_documents_to_process(
        limit=PROCESS_LIMIT,
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
        "Dokumentów:",
        len(documents)
    )

    if not documents:

        print(
            "Brak dokumentów do pracy."
        )

        return

    for (
        doc_id,
        url,
        status,
        attempts
    ) in documents:

        print(
            doc_id,
            "|",
            status,
            "| attempts:",
            attempts
        )

    # --------------------------------------------------------
    # 3. Сессия CBOSA
    # --------------------------------------------------------

    print(
        "\nOtwieram CBOSA..."
    )

    open_cbosa()

    time.sleep(2)

    successful = 0
    failed = 0

    # --------------------------------------------------------
    # 4. Документы
    # --------------------------------------------------------

    for index, row in enumerate(
        documents,
        start=1
    ):

        (
            doc_id,
            url,
            previous_status,
            previous_attempts
        ) = row

        print(
            "\n========================================"
        )

        print(
            f"DOKUMENT {index}/"
            f"{len(documents)}"
        )

        print(
            "========================================"
        )

        print(
            "ID:",
            doc_id
        )

        print(
            "Poprzedni status:",
            previous_status
        )

        print(
            "Poprzednie nieudane próby:",
            previous_attempts
        )

        try:

            # ================================================
            # A. DOWNLOAD
            # ================================================

            print(
                "\n1. Download..."
            )

            html_bytes = (
                download_document(
                    url
                )
            )

            print(
                "Bytes:",
                len(html_bytes)
            )

            # ================================================
            # B. RAW HTML
            # ================================================

            if SAVE_RAW_HTML:

                path = save_raw_html(
                    doc_id,
                    html_bytes
                )

                print(
                    "Raw HTML:",
                    path
                )

            # ================================================
            # C. DECODE
            # ================================================

            html_text = (
                html_bytes.decode(
                    "utf-8",
                    errors="replace"
                )
            )

            # ================================================
            # D. PARSE
            # ================================================

            print(
                "\n2. Parse..."
            )

            parsed_data = (
                parse_document(
                    html_text
                )
            )

            print(
                "Sygnatura:",
                parsed_data.get(
                    "sygnatura"
                )
            )

            # ================================================
            # E. VALIDATION
            # ================================================

            print(
                "\n3. Walidacja..."
            )

            validate_document(
                parsed_data
            )

            print(
                "Walidacja OK."
            )

            # ================================================
            # F. CREATE RESULT
            # ================================================

            result = {
                "doc_id":
                    doc_id,

                "url":
                    url,

                **parsed_data,
            }

            # ================================================
            # G. SQLITE
            #
            # result + DONE
            # w jednej transakcji.
            # ================================================

            print(
                "\n4. Zapis SQLite..."
            )

            save_document_result(
                doc_id,
                result
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
        # Пауза
        # ----------------------------------------------------

        if index < len(documents):

            print(
                f"\nCzekam "
                f"{DOCUMENT_DELAY} sek..."
            )

            time.sleep(
                DOCUMENT_DELAY
            )

    # --------------------------------------------------------
    # 5. Итог
    # --------------------------------------------------------

    print(
        "\n========================================"
    )

    print(
        "KONIEC"
    )

    print(
        "========================================"
    )

    print(
        "OK:",
        successful
    )

    print(
        "Błędy:",
        failed
    )

    print_statistics()


if __name__ == "__main__":
    main()
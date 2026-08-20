import json
import os
import time

from cbosa_client import (
    BASE_URL,
    open_cbosa,
    request_with_retry,
)

from database import (
    create_database,
    get_pending_documents,
    mark_done,
    mark_failed,
    count_documents,
    count_by_status,
)

from parse_document import parse_document


# ============================================================
# USTAWIENIA
# ============================================================

# Пока обрабатываем только 3 документа за один запуск.
PROCESS_LIMIT = 3

# Пауза между отдельными orzeczeniami.
DOCUMENT_DELAY = 6

# Итоговый тестовый файл.
OUTPUT_FILE = "results.jsonl"

# Папка с исходным HTML.
RAW_HTML_DIR = "raw_html"

# Для тестов сохраняем HTML.
SAVE_RAW_HTML = True

# Такой Referer мы уже проверили экспериментально.
DOC_REFERER = f"{BASE_URL}/pl/cbo/search"


# ============================================================
# POBIERANIE DOKUMENTU
# ============================================================

def download_document(url):
    """
    Pobiera HTML pojedynczego orzeczenia.

    Korzystamy z tej samej sesji HTTP,
    której używa cbosa_client.py.
    """

    response = request_with_retry(
        "GET",
        url,
        headers={
            "Referer": DOC_REFERER,
        },
    )

    return response.content


# ============================================================
# ZAPIS ORYGINALNEGO HTML
# ============================================================

def save_raw_html(
    doc_id,
    html_bytes
):
    """
    Zapisuje oryginalny HTML dokumentu.

    Jest to przydatne podczas tworzenia
    i testowania parsera.
    """

    os.makedirs(
        RAW_HTML_DIR,
        exist_ok=True
    )

    file_path = os.path.join(
        RAW_HTML_DIR,
        f"{doc_id}.html"
    )

    with open(
        file_path,
        "wb"
    ) as file:

        file.write(
            html_bytes
        )

    return file_path


# ============================================================
# ZAPIS WYNIKU
# ============================================================

def save_result(
    doc_id,
    url,
    parsed_data
):
    """
    Zapisuje jeden dokument jako jedną linię JSON.

    Format JSONL:
    1 linia = 1 orzeczenie.
    """

    record = {
        "doc_id": doc_id,
        "url": url,
        **parsed_data,
    }

    with open(
        OUTPUT_FILE,
        "a",
        encoding="utf-8"
    ) as file:

        file.write(
            json.dumps(
                record,
                ensure_ascii=False
            )
        )

        file.write("\n")


# ============================================================
# WYŚWIETLENIE STATYSTYK
# ============================================================

def print_statistics():
    """
    Pokazuje aktualny stan naszej bazy.
    """

    print(
        "\n========================================"
    )

    print(
        "STATYSTYKI SQLITE"
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
        "CBOSA - PRZETWARZANIE DOKUMENTÓW"
    )

    print(
        "========================================"
    )

    # --------------------------------------------------------
    # 1. Убеждаемся, что база существует.
    # --------------------------------------------------------

    create_database()

    print_statistics()

    # --------------------------------------------------------
    # 2. Берём только pending.
    # --------------------------------------------------------

    documents = get_pending_documents(
        limit=PROCESS_LIMIT
    )

    print(
        "\n========================================"
    )

    print(
        "DOKUMENTY DO PRZETWORZENIA"
    )

    print(
        "========================================"
    )

    print(
        "Pobrano z bazy:",
        len(documents)
    )

    if not documents:

        print(
            "Brak dokumentów ze statusem pending."
        )

        return

    for doc_id, url in documents:

        print(
            doc_id,
            url
        )

    # --------------------------------------------------------
    # 3. Открываем CBOSA один раз.
    # --------------------------------------------------------

    print(
        "\n========================================"
    )

    print(
        "OTWIERAM CBOSA"
    )

    print(
        "========================================"
    )

    open_cbosa()

    print(
        "CBOSA otwarta."
    )

    time.sleep(2)

    successful = 0
    failed = 0

    # --------------------------------------------------------
    # 4. Обрабатываем документы по очереди.
    # --------------------------------------------------------

    for index, (
        doc_id,
        url
    ) in enumerate(
        documents,
        start=1
    ):

        print(
            "\n========================================"
        )

        print(
            f"DOKUMENT {index}/{len(documents)}"
        )

        print(
            "========================================"
        )

        print(
            "ID:",
            doc_id
        )

        print(
            "URL:",
            url
        )

        try:

            # ------------------------------------------------
            # A. Скачать документ.
            # ------------------------------------------------

            print(
                "\n1. Pobieram HTML..."
            )

            html_bytes = download_document(
                url
            )

            print(
                "Pobrano:",
                len(html_bytes),
                "bytes"
            )

            # ------------------------------------------------
            # B. Сохранить исходный HTML.
            # ------------------------------------------------

            if SAVE_RAW_HTML:

                html_path = save_raw_html(
                    doc_id,
                    html_bytes
                )

                print(
                    "HTML zapisany:",
                    html_path
                )

            # ------------------------------------------------
            # C. Превратить bytes → текст.
            # ------------------------------------------------

            html_text = html_bytes.decode(
                "utf-8",
                errors="replace"
            )

            # ------------------------------------------------
            # D. Распарсить HTML.
            # ------------------------------------------------

            print(
                "\n2. Parsuję dokument..."
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

            print(
                "Sąd:",
                parsed_data.get(
                    "sad"
                )
            )

            print(
                "Data:",
                parsed_data.get(
                    "data_orzeczenia"
                )
            )

            # ------------------------------------------------
            # E. Проверка результата.
            # ------------------------------------------------

            if not parsed_data.get(
                "sygnatura"
            ):

                raise RuntimeError(
                    "Parser nie znalazł sygnatury."
                )

            # ------------------------------------------------
            # F. Запись результата.
            # ------------------------------------------------

            print(
                "\n3. Zapisuję wynik..."
            )

            save_result(
                doc_id,
                url,
                parsed_data
            )

            # ------------------------------------------------
            # G. Только после успешного сохранения ставим done.
            # ------------------------------------------------

            mark_done(
                doc_id
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
        # Между документами небольшая пауза.
        # ----------------------------------------------------

        if index < len(
            documents
        ):

            print(
                f"\nCzekam "
                f"{DOCUMENT_DELAY} sek..."
            )

            time.sleep(
                DOCUMENT_DELAY
            )

    # --------------------------------------------------------
    # 5. Итог.
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
        "Poprawnie w tym uruchomieniu:",
        successful
    )

    print(
        "Błędy w tym uruchomieniu:",
        failed
    )

    print_statistics()


if __name__ == "__main__":
    main()
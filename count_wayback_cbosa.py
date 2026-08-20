import json
import re
import time

import requests


# ============================================================
# USTAWIENIA
# ============================================================

CDX_URL = (
    "https://web.archive.org"
    "/cdx/search/cdx"
)

TARGET_PREFIX = (
    "orzeczenia.nsa.gov.pl/doc/"
)

# Ile unikalnych URL prosimy w jednym kawałku.
#
# Wayback obsługuje resumeKey,
# więc nie pobieramy wszystkiego jednym
# gigantycznym response.

LIMIT = 5000


# Ostrożna pauza między kolejnymi stronami.
REQUEST_DELAY = 3


MAX_RETRIES = 5


OUTPUT_FILE = (
    "wayback_cbosa_doc_ids.txt"
)


HEADERS = {
    "User-Agent":
        "cbosa-coverage-research/0.1 "
        "(small public archive index study)"
}


session = requests.Session()

session.headers.update(
    HEADERS
)


# ============================================================
# HTTP
# ============================================================

def request_page(
    resume_key=None
):

    params = {
        "url":
            TARGET_PREFIX,

        "matchType":
            "prefix",

        "output":
            "json",

        # urlkey обязательно оставляем:
        # он нужен для надёжной работы resumeKey.
        "fl":
            "urlkey,original",

        "filter": [
        "statuscode:200",
        "mimetype:text/html",
    ],

        # Оставляем только первый capture
        # каждого уникального URL.
        "collapse":
            "urlkey",

        "limit":
            LIMIT,

        "showResumeKey":
            "true",
    }

    if resume_key:

        params[
            "resumeKey"
        ] = resume_key

    for attempt in range(
        1,
        MAX_RETRIES + 1
    ):

        try:

            response = session.get(
                CDX_URL,
                params=params,
                timeout=180
            )

        except requests.RequestException as error:

            print(
                "Błąd połączenia:",
                type(error).__name__,
                error
            )

            if attempt == MAX_RETRIES:

                raise

            wait = attempt * 15

            print(
                f"Czekam {wait} sek..."
            )

            time.sleep(
                wait
            )

            continue

        if response.status_code == 200:

            return response

        if response.status_code in (
            429,
            500,
            502,
            503,
            504,
        ):

            print(
                "HTTP:",
                response.status_code
            )

            if attempt == MAX_RETRIES:

                response.raise_for_status()

            wait = attempt * 20

            print(
                f"Czekam {wait} sek..."
            )

            time.sleep(
                wait
            )

            continue

        response.raise_for_status()

    raise RuntimeError(
        "Nie udało się pobrać strony CDX."
    )


# ============================================================
# PARSER RESPONSE
# ============================================================

def parse_page(
    response
):
    """
    JSON z showResumeKey może wyglądać:

    [
        ["urlkey", "original"],
        ["...", "..."],
        ["...", "..."],
        [],
        ["RESUME_KEY"]
    ]

    Oddzielamy normalne rekordy
    od resume key.
    """

    data = response.json()

    if not data:

        return [], None

    headers = data[0]

    records = []

    resume_key = None

    for item in data[1:]:

        if not isinstance(
            item,
            list
        ):

            continue

        # Pusta linia przed resume key.
        if len(item) == 0:

            continue

        # Resume key ma tylko jedno pole.
        if len(item) == 1:

            resume_key = item[0]

            continue

        # Normalny record.
        if len(item) == len(
            headers
        ):

            record = dict(
                zip(
                    headers,
                    item
                )
            )

            records.append(
                record
            )

    return (
        records,
        resume_key
    )


# ============================================================
# DOC ID
# ============================================================

def extract_doc_id(
    original
):

    if not original:

        return None

    match = re.search(
        r"/doc/([A-Za-z0-9]+)",
        original
    )

    if not match:

        return None

    return (
        match
        .group(1)
        .upper()
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "========================================"
    )

    print(
        "WAYBACK CBOSA COVERAGE"
    )

    print(
        "========================================"
    )

    print(
        "Prefix:",
        TARGET_PREFIX
    )

    print(
        "Limit / request:",
        LIMIT
    )

    print()

    # Перезаписываем старый тестовый файл.

    output = open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    )

    page_number = 0

    record_count = 0

    doc_count = 0

    resume_key = None

    start = time.perf_counter()

    try:

        while True:

            page_number += 1

            print(
                "\n========================================"
            )

            print(
                f"PAGE {page_number}"
            )

            print(
                "========================================"
            )

            response = request_page(
                resume_key
            )

            records, new_resume_key = (
                parse_page(
                    response
                )
            )

            print(
                "Records:",
                len(records)
            )

            page_docs = 0

            for record in records:

                original = record.get(
                    "original"
                )

                doc_id = extract_doc_id(
                    original
                )

                if not doc_id:

                    continue

                output.write(
                    doc_id + "\n"
                )

                page_docs += 1

            output.flush()

            record_count += len(
                records
            )

            doc_count += page_docs

            elapsed = (
                time.perf_counter()
                - start
            )

            print(
                "Doc IDs this page:",
                page_docs
            )

            print(
                "TOTAL doc IDs:",
                doc_count
            )

            print(
                f"Elapsed: "
                f"{elapsed:.1f} s"
            )

            # ----------------------------------------
            # Если resume key нет —
            # дошли до конца.
            # ----------------------------------------

            if not new_resume_key:

                print(
                    "\nBrak resumeKey."
                )

                print(
                    "Koniec danych."
                )

                break

            resume_key = (
                new_resume_key
            )

            print(
                "Resume key: TAK"
            )

            print(
                f"Czekam "
                f"{REQUEST_DELAY} sek..."
            )

            time.sleep(
                REQUEST_DELAY
            )

    finally:

        output.close()

    total_time = (
        time.perf_counter()
        - start
    )

    print(
        "\n========================================"
    )

    print(
        "WYNIK"
    )

    print(
        "========================================"
    )

    print(
        "Pages:",
        page_number
    )

    print(
        "Records:",
        record_count
    )

    print(
        "Wayback CBOSA doc IDs:",
        doc_count
    )

    print(
        f"Cały czas: "
        f"{total_time:.1f} s"
    )

    print(
        "Zapisano:",
        OUTPUT_FILE
    )


if __name__ == "__main__":
    main()
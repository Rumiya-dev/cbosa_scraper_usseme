import gzip
import time

import duckdb
import requests


# ============================================================
# USTAWIENIA
# ============================================================

# Jeden konkretny crawl Common Crawl.
#
# Na razie testujemy tylko jeden miesiąc.
# Jeśli metoda zadziała, później sprawdzimy
# wiele crawlów i połączymy wyniki.

CRAWL = "CC-MAIN-2026-30"


DATA_BASE = (
    "https://data.commoncrawl.org/"
)


# Ten plik zawiera listę wszystkich plików
# indeksu dla danego crawla.
#
# W środku są różne subsety:
# - warc
# - robotstxt
# - crawldiagnostics
#
# Nas interesuje TYLKO subset=warc.

PATHS_URL = (
    f"{DATA_BASE}"
    f"crawl-data/{CRAWL}/"
    f"cc-index-table.paths.gz"
)


# ============================================================
# 10 TESTOWYCH ID Z JUDDGES / HUGGING FACE
# ============================================================

SAMPLE_DOC_IDS = [
    "6447E5BA57",
    "9C5555C2A1",
    "1A1AAF78BF",
    "35CA817E7C",
    "2104ED178E",
    "E43FA98433",
    "0ADFAC8D4A",
    "4B9553DF1E",
    "5FAEF32649",
    "A6B27D39A9",
]


# ============================================================
# DOWNLOAD LISTY PARQUET
# ============================================================

def download_paths():

    print(
        "========================================"
    )

    print(
        "COMMON CRAWL URL INDEX"
    )

    print(
        "========================================"
    )

    print(
        "Crawl:",
        CRAWL
    )

    print(
        "\nPobieram listę plików Parquet..."
    )

    response = requests.get(
        PATHS_URL,
        timeout=120
    )

    response.raise_for_status()

    # Plik jest gzip.
    # Rozpakowujemy go w pamięci.

    text = gzip.decompress(
        response.content
    ).decode(
        "utf-8"
    )

    # ========================================================
    # WSZYSTKIE ŚCIEŻKI
    # ========================================================

    all_paths = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    print(
        "Wszystkich ścieżek:",
        len(all_paths)
    )

    # ========================================================
    # TYLKO subset=warc
    # ========================================================

    paths = [
        path
        for path in all_paths
        if (
            f"crawl={CRAWL}/subset=warc/"
            in path

            and

            path.endswith(
                ".parquet"
            )
        )
    ]

    print(
        "Tylko subset=warc:",
        len(paths)
    )

    # Jeśli wyszło 0,
    # nie próbujemy iść dalej.

    if not paths:

        raise RuntimeError(
            "Nie znaleziono plików subset=warc."
        )

    # ========================================================
    # BUDOWANIE PEŁNYCH URL
    # ========================================================

    parquet_urls = []

    for path in paths:

        # Usuwamy ewentualny początkowy "/".

        clean_path = (
            path.lstrip("/")
        )

        # Lista Common Crawl zazwyczaj zawiera:
        #
        # cc-index/table/...
        #
        # więc wystarczy dokleić DATA_BASE.

        url = (
            DATA_BASE
            + clean_path
        )

        parquet_urls.append(
            url
        )

    print(
        "Parquet URLs:",
        len(parquet_urls)
    )

    print(
        "\nPierwszy plik:"
    )

    print(
        parquet_urls[0]
    )

    print(
        "\nOstatni plik:"
    )

    print(
        parquet_urls[-1]
    )

    return parquet_urls


# ============================================================
# DUCKDB
# ============================================================

def create_commoncrawl_view(
    parquet_urls
):

    print(
        "\n========================================"
    )

    print(
        "DUCKDB"
    )

    print(
        "========================================"
    )

    connection = (
        duckdb.connect()
    )

    # ========================================================
    # HTTPFS
    #
    # DuckDB będzie czytał Parquet bezpośrednio
    # przez HTTPS z Common Crawl.
    # ========================================================

    try:

        connection.execute(
            "LOAD httpfs"
        )

    except Exception:

        print(
            "Instaluję rozszerzenie httpfs..."
        )

        connection.execute(
            "INSTALL httpfs"
        )

        connection.execute(
            "LOAD httpfs"
        )

    # Więcej automatycznych prób
    # przy chwilowym problemie HTTP.

    connection.execute(
        "SET http_retries = 20"
    )

    # DuckDB może pokazywać pasek postępu.

    connection.execute(
        "SET enable_progress_bar = true"
    )

    print(
        "\nTworzę widok URL Index..."
    )

    print(
        "Plików do otwarcia:",
        len(parquet_urls)
    )

    print(
        "To może potrwać kilka minut."
    )

    start = (
        time.perf_counter()
    )

    # ========================================================
    # WAŻNE:
    #
    # Nie używamy union_by_name=True.
    #
    # Wszystkie pliki należą teraz
    # do tego samego subset=warc.
    # ========================================================

    retries_left = 3

    while True:

        try:

            relation = (
                connection.read_parquet(
                    parquet_urls,
                    hive_partitioning=True,
                )
            )

            relation.create_view(
                "ccindex"
            )

            break

        except (
            duckdb.HTTPException,
            duckdb.InvalidInputException,
        ) as error:

            print(
                "\nBłąd przy otwieraniu Parquet:"
            )

            print(
                repr(error)
            )

            if retries_left <= 0:

                connection.close()

                raise

            retries_left -= 1

            print(
                "Czekam 15 sekund "
                "i próbuję ponownie..."
            )

            time.sleep(
                15
            )

    elapsed = (
        time.perf_counter()
        - start
    )

    print(
        "Widok gotowy."
    )

    print(
        f"Czas tworzenia widoku: "
        f"{elapsed:.2f} s"
    )

    return connection


# ============================================================
# TEST 10 KONKRETNYCH ID
# ============================================================

def check_sample_ids(
    connection
):

    print(
        "\n========================================"
    )

    print(
        "TEST 10 ID Z JUDDGES"
    )

    print(
        "========================================"
    )

    print(
        "Szukam 10 konkretnych dokumentów..."
    )

    # Zamieniamy:
    #
    # 6447E5BA57
    #
    # na:
    #
    # /doc/6447E5BA57

    paths = [
        f"/doc/{doc_id}"
        for doc_id
        in SAMPLE_DOC_IDS
    ]

    # ?, ?, ?, ...
    #
    # Dzięki temu bezpiecznie
    # przekazujemy wartości do SQL.

    placeholders = (
        ", ".join(
            ["?"]
            * len(paths)
        )
    )

    query = f"""
        SELECT DISTINCT

            url_path,
            fetch_time,
            warc_filename,
            warc_record_offset,
            warc_record_length

        FROM ccindex

        WHERE
            crawl = ?

            AND subset = 'warc'

            AND url_host_tld = 'pl'

            AND
            url_host_registered_domain
                = 'nsa.gov.pl'

            AND
            url_host_name
                = 'orzeczenia.nsa.gov.pl'

            AND
            fetch_status = 200

            AND
            url_path IN (
                {placeholders}
            )

        ORDER BY
            url_path,
            fetch_time DESC
    """

    params = [
        CRAWL,
        *paths,
    ]

    start = (
        time.perf_counter()
    )

    rows = (
        connection
        .execute(
            query,
            params
        )
        .fetchall()
    )

    elapsed = (
        time.perf_counter()
        - start
    )

    # ========================================================
    # KTÓRE ZNALEZIONO
    # ========================================================

    found_paths = {
        row[0]
        for row in rows
    }

    print(
        "\n----------------------------------------"
    )

    for doc_id in SAMPLE_DOC_IDS:

        path = (
            f"/doc/{doc_id}"
        )

        status = (
            "HIT"
            if path in found_paths
            else "MISS"
        )

        print(
            doc_id,
            status
        )

    print(
        "----------------------------------------"
    )

    print(
        "\nZnalezionych:",
        len(found_paths),
        "/",
        len(SAMPLE_DOC_IDS)
    )

    print(
        f"Czas zapytania: "
        f"{elapsed:.2f} s"
    )

    # ========================================================
    # JEŚLI COŚ ZNALEZIONO
    #
    # pokazujemy współrzędne rekordu WARC.
    # ========================================================

    if rows:

        print(
            "\n========================================"
        )

        print(
            "PRZYKŁADOWE WARC RECORDS"
        )

        print(
            "========================================"
        )

        for row in rows[:10]:

            (
                url_path,
                fetch_time,
                warc_filename,
                warc_offset,
                warc_length,
            ) = row

            print(
                "\nURL path:",
                url_path
            )

            print(
                "Fetch time:",
                fetch_time
            )

            print(
                "WARC:",
                warc_filename
            )

            print(
                "Offset:",
                warc_offset
            )

            print(
                "Length:",
                warc_length
            )

    return rows


# ============================================================
# LICZENIE WSZYSTKICH CBOSA /doc/
# ============================================================

def count_cbosa_documents(
    connection
):

    print(
        "\n========================================"
    )

    print(
        "LICZĘ CBOSA /doc/"
    )

    print(
        "========================================"
    )

    print(
        "Sprawdzam ile stron /doc/ "
        "z CBOSA istnieje w tym crawlu."
    )

    print(
        "To może potrwać kilka minut..."
    )

    query = """
        SELECT

            COUNT(*) AS captures,

            COUNT(
                DISTINCT url_path
            ) AS unique_doc_paths,

            MIN(fetch_time)
                AS first_capture,

            MAX(fetch_time)
                AS last_capture

        FROM ccindex

        WHERE
            crawl = ?

            AND subset = 'warc'

            AND url_host_tld = 'pl'

            AND
            url_host_registered_domain
                = 'nsa.gov.pl'

            AND
            url_host_name
                = 'orzeczenia.nsa.gov.pl'

            AND
            url_path LIKE '/doc/%'

            AND
            fetch_status = 200
    """

    start = (
        time.perf_counter()
    )

    result = (
        connection
        .execute(
            query,
            [CRAWL]
        )
        .fetchone()
    )

    elapsed = (
        time.perf_counter()
        - start
    )

    (
        captures,
        unique_docs,
        first_capture,
        last_capture,
    ) = result

    print(
        "\n========================================"
    )

    print(
        "WYNIK COMMON CRAWL"
    )

    print(
        "========================================"
    )

    print(
        "Crawl:",
        CRAWL
    )

    print(
        "Captures:",
        captures
    )

    print(
        "Unique /doc/:",
        unique_docs
    )

    print(
        "First capture:",
        first_capture
    )

    print(
        "Last capture:",
        last_capture
    )

    print(
        f"Czas zapytania: "
        f"{elapsed:.2f} s"
    )

    return unique_docs


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "========================================"
    )

    print(
        "CBOSA + COMMON CRAWL PROBE"
    )

    print(
        "========================================"
    )

    # ========================================================
    # 1. Pobieramy poprawną listę
    #    subset=warc
    # ========================================================

    parquet_urls = (
        download_paths()
    )

    # ========================================================
    # 2. DuckDB otwiera URL Index
    # ========================================================

    connection = (
        create_commoncrawl_view(
            parquet_urls
        )
    )

    try:

        # ====================================================
        # 3. Najpierw szybciej sprawdzamy
        #    10 znanych ID.
        # ====================================================

        check_sample_ids(
            connection
        )

        # ====================================================
        # 4. Potem liczymy wszystkie
        #    CBOSA /doc/ w tym crawlu.
        # ====================================================

        count_cbosa_documents(
            connection
        )

    finally:

        connection.close()

    print(
        "\n========================================"
    )

    print(
        "KONIEC TESTU"
    )

    print(
        "========================================"
    )


if __name__ == "__main__":
    main()
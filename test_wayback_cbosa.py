import json
import time

import requests


# ============================================================
# USTAWIENIA
# ============================================================

CDX_URL = (
    "https://web.archive.org"
    "/cdx/search/cdx"
)

WAYBACK_BASE = (
    "https://web.archive.org/web/"
)


# 10 ID, które wcześniej pobraliśmy
# z JuDDGES / Hugging Face.
#
# Są z różnych części datasetu.

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


# ------------------------------------------------------------
# Ostrożna przerwa między zapytaniami do Wayback.
# ------------------------------------------------------------

REQUEST_DELAY = 3


# Ile razy próbujemy ponownie
# przy chwilowym problemie sieciowym.

MAX_RETRIES = 3


HEADERS = {
    "User-Agent":
        "cbosa-research-test/0.1 "
        "(small archival coverage test)"
}


session = requests.Session()

session.headers.update(
    HEADERS
)


# ============================================================
# REQUEST Z RETRY
# ============================================================

def request_with_retry(
    url,
    params=None,
    timeout=60
):

    for attempt in range(
        1,
        MAX_RETRIES + 1
    ):

        try:

            response = session.get(
                url,
                params=params,
                timeout=timeout,
                allow_redirects=True
            )

        except requests.RequestException as error:

            print(
                "    Błąd połączenia:"
            )

            print(
                "   ",
                type(error).__name__,
                error
            )

            if attempt == MAX_RETRIES:

                return None

            wait = (
                attempt * 10
            )

            print(
                f"    Czekam {wait} sek..."
            )

            time.sleep(
                wait
            )

            continue

        # --------------------------------------------
        # OK
        # --------------------------------------------

        if response.status_code == 200:

            return response

        # --------------------------------------------
        # Chwilowe problemy / rate limiting
        # --------------------------------------------

        if response.status_code in (
            429,
            500,
            502,
            503,
            504,
        ):

            print(
                "    HTTP:",
                response.status_code
            )

            if attempt == MAX_RETRIES:

                return response

            wait = (
                attempt * 15
            )

            print(
                f"    Czekam {wait} sek..."
            )

            time.sleep(
                wait
            )

            continue

        # --------------------------------------------
        # Inny status.
        # --------------------------------------------

        return response

    return None


# ============================================================
# PARSOWANIE CDX JSON
# ============================================================

def parse_cdx_json(
    response
):

    if response is None:

        return []

    if response.status_code != 200:

        return []

    try:

        data = response.json()

    except json.JSONDecodeError:

        return []

    # Wayback JSON ma postać:
    #
    # [
    #   ["timestamp", "original", ...],
    #   ["202001...", "http://...", ...],
    #   ...
    # ]
    #
    # Pierwsza linia to nagłówki.

    if (
        not isinstance(
            data,
            list
        )
        or len(data) < 2
    ):

        return []

    headers = data[0]

    results = []

    for row in data[1:]:

        if len(row) != len(headers):

            continue

        item = dict(
            zip(
                headers,
                row
            )
        )

        results.append(
            item
        )

    return results


# ============================================================
# SZUKANIE JEDNEGO DOC_ID
# ============================================================

def find_document_captures(
    doc_id
):

    target = (
        "orzeczenia.nsa.gov.pl"
        f"/doc/{doc_id}"
    )

    params = {
        "url":
            target,

        "output":
            "json",

        "fl":
            (
                "timestamp,"
                "original,"
                "statuscode,"
                "mimetype,"
                "digest,"
                "length"
            ),

        "filter":
            "statuscode:200",

        # Kilka capture wystarczy.
        "limit":
            10,
    }

    response = request_with_retry(
        CDX_URL,
        params=params,
        timeout=60
    )

    if response is None:

        return [], None

    return (
        parse_cdx_json(
            response
        ),
        response.status_code
    )


# ============================================================
# WYBÓR CAPTURE
# ============================================================

def choose_capture(
    captures
):

    if not captures:

        return None

    # Bierzemy najnowszy capture.

    captures = sorted(
        captures,
        key=lambda item:
            item.get(
                "timestamp",
                ""
            ),
        reverse=True
    )

    return captures[0]


# ============================================================
# RAW HTML Z WAYBACK
# ============================================================

def download_archived_html(
    capture
):

    timestamp = capture.get(
        "timestamp"
    )

    original = capture.get(
        "original"
    )

    if (
        not timestamp
        or not original
    ):

        raise RuntimeError(
            "Brak timestamp/original."
        )

    # --------------------------------------------------------
    # id_ oznacza replay bez normalnego
    # paska / wrappera Wayback.
    #
    # Chcemy dostać możliwie oryginalny
    # archived response.
    # --------------------------------------------------------

    archive_url = (
        f"{WAYBACK_BASE}"
        f"{timestamp}id_/"
        f"{original}"
    )

    print(
        "\nPobieram archived HTML:"
    )

    print(
        archive_url
    )

    response = request_with_retry(
        archive_url,
        timeout=120
    )

    if response is None:

        raise RuntimeError(
            "Brak odpowiedzi Wayback."
        )

    if response.status_code != 200:

        raise RuntimeError(
            "Wayback HTTP "
            f"{response.status_code}"
        )

    return (
        response.content,
        archive_url
    )


# ============================================================
# TEST NASZEGO PARSERA
# ============================================================

def test_parser(
    html_bytes
):

    print(
        "\n========================================"
    )

    print(
        "TEST PARSE_DOCUMENT.PY"
    )

    print(
        "========================================"
    )

    try:

        from parse_document import (
            parse_document
        )

    except Exception as error:

        print(
            "Błąd importu parsera:"
        )

        print(
            type(error).__name__,
            error
        )

        return

    html_text = html_bytes.decode(
        "utf-8",
        errors="replace"
    )

    try:

        result = parse_document(
            html_text
        )

    except Exception as error:

        print(
            "Parser ERROR:"
        )

        print(
            type(error).__name__,
            error
        )

        return

    print(
        "Tytuł:",
        result.get(
            "tytul"
        )
    )

    print(
        "Sygnatura:",
        result.get(
            "sygnatura"
        )
    )

    print(
        "Sąd:",
        result.get(
            "sad"
        )
    )

    print(
        "Data:",
        result.get(
            "data_orzeczenia"
        )
    )

    sentencja = result.get(
        "sentencja_html"
    )

    uzasadnienie = result.get(
        "uzasadnienie_html"
    )

    print(
        "Sentencja HTML:",
        "OK"
        if sentencja
        else "BRAK"
    )

    print(
        "Uzasadnienie HTML:",
        "OK"
        if uzasadnienie
        else "BRAK"
    )

    if sentencja:

        print(
            "Sentencja length:",
            len(sentencja)
        )

    if uzasadnienie:

        print(
            "Uzasadnienie length:",
            len(uzasadnienie)
        )


# ============================================================
# PREFIX PROBE
# ============================================================

def prefix_probe():
    """
    Jedno małe zapytanie prefix.

    NIE próbujemy tutaj pobrać całej listy.

    Chcemy tylko odpowiedzieć na pytanie:

    Czy Wayback ma w ogóle archived URLs
    pod orzeczenia.nsa.gov.pl/doc/ ?
    """

    print(
        "\n========================================"
    )

    print(
        "PREFIX PROBE /doc/"
    )

    print(
        "========================================"
    )

    params = {
        "url":
            (
                "orzeczenia.nsa.gov.pl"
                "/doc/"
            ),

        "matchType":
            "prefix",

        "output":
            "json",

        "fl":
            (
                "timestamp,"
                "original,"
                "statuscode,"
                "mimetype"
            ),

        "filter":
            "statuscode:200",

        # Celowo mało.
        #
        # Nie chcemy teraz masowej kwerendy.
        "limit":
            20,
    }

    response = request_with_retry(
        CDX_URL,
        params=params,
        timeout=120
    )

    if response is None:

        print(
            "Prefix probe: brak odpowiedzi."
        )

        return

    print(
        "HTTP:",
        response.status_code
    )

    if response.status_code != 200:

        print(
            "Prefix probe nie powiódł się."
        )

        return

    results = parse_cdx_json(
        response
    )

    print(
        "Wyników:",
        len(results)
    )

    if results:

        print(
            "\nPrzykładowe archived URLs:"
        )

        for item in results[:10]:

            print(
                item.get(
                    "timestamp"
                ),
                item.get(
                    "original"
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
        "CBOSA + WAYBACK PROBE"
    )

    print(
        "========================================"
    )

    found = []

    first_capture = None

    # ========================================================
    # 1. Dokładne sprawdzenie 10 ID
    # ========================================================

    for index, doc_id in enumerate(
        SAMPLE_DOC_IDS,
        start=1
    ):

        print(
            "\n----------------------------------------"
        )

        print(
            f"DOC {index}/"
            f"{len(SAMPLE_DOC_IDS)}"
        )

        print(
            "doc_id:",
            doc_id
        )

        captures, http_status = (
            find_document_captures(
                doc_id
            )
        )

        if http_status is not None:

            print(
                "CDX HTTP:",
                http_status
            )

        if captures:

            capture = (
                choose_capture(
                    captures
                )
            )

            print(
                ">>> HIT"
            )

            print(
                "Captures:",
                len(captures)
            )

            print(
                "Timestamp:",
                capture.get(
                    "timestamp"
                )
            )

            print(
                "Original:",
                capture.get(
                    "original"
                )
            )

            print(
                "Mimetype:",
                capture.get(
                    "mimetype"
                )
            )

            found.append(
                {
                    "doc_id":
                        doc_id,

                    "capture":
                        capture,
                }
            )

            if first_capture is None:

                first_capture = (
                    capture
                )

        else:

            print(
                ">>> MISS"
            )

        # Nie robimy 10 requestów
        # jeden za drugim.

        if index < len(
            SAMPLE_DOC_IDS
        ):

            print(
                f"Czekam "
                f"{REQUEST_DELAY} sek..."
            )

            time.sleep(
                REQUEST_DELAY
            )

    # ========================================================
    # 2. Podsumowanie
    # ========================================================

    total = len(
        SAMPLE_DOC_IDS
    )

    hit_count = len(
        found
    )

    hit_rate = (
        hit_count
        / total
        * 100
        if total
        else 0
    )

    print(
        "\n========================================"
    )

    print(
        "WYNIK EXACT TEST"
    )

    print(
        "========================================"
    )

    print(
        "Sprawdzonych:",
        total
    )

    print(
        "HIT:",
        hit_count
    )

    print(
        "MISS:",
        total - hit_count
    )

    print(
        f"Hit rate: "
        f"{hit_rate:.1f}%"
    )

    # ========================================================
    # 3. Zapis wyników
    # ========================================================

    with open(
        "wayback_probe_results.json",
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            found,
            file,
            ensure_ascii=False,
            indent=2
        )

    print(
        "Zapisano:"
        " wayback_probe_results.json"
    )

    # ========================================================
    # 4. Jeśli mamy capture:
    #    pobieramy prawdziwy archived HTML.
    # ========================================================

    if first_capture is not None:

        try:

            html_bytes, archive_url = (
                download_archived_html(
                    first_capture
                )
            )

            print(
                "HTML bytes:",
                len(
                    html_bytes
                )
            )

            with open(
                "wayback_sample.html",
                "wb"
            ) as file:

                file.write(
                    html_bytes
                )

            print(
                "Zapisano:"
                " wayback_sample.html"
            )

            print(
                "Archive URL:",
                archive_url
            )

            # --------------------------------------------
            # 5. Sprawdzamy nasz parser.
            # --------------------------------------------

            test_parser(
                html_bytes
            )

        except Exception as error:

            print(
                "\nBłąd pobierania / "
                "testowania HTML:"
            )

            print(
                type(error).__name__,
                error
            )

    else:

        print(
            "\nNie znaleziono żadnego "
            "z 10 exact ID."
        )

    # ========================================================
    # 6. Jeden mały prefix probe.
    #
    # Nawet jeśli 10 losowych ID = MISS,
    # sprawdzamy czy Wayback posiada
    # jakiekolwiek /doc/ z CBOSA.
    # ========================================================

    print(
        f"\nCzekam "
        f"{REQUEST_DELAY} sek "
        "przed prefix probe..."
    )

    time.sleep(
        REQUEST_DELAY
    )

    prefix_probe()

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
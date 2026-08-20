import io
import json
import re
import time

import requests
from warcio.archiveiterator import ArchiveIterator


# ============================================================
# USTAWIENIA
# ============================================================

HF_DATASET = "JuDDGES/pl-nsa-enriched"

HF_API = (
    "https://datasets-server.huggingface.co"
)

CC_COLLECTIONS_URL = (
    "https://index.commoncrawl.org/collinfo.json"
)

CC_DATA_BASE = (
    "https://data.commoncrawl.org/"
)


# Сколько документов проверяем.
SAMPLE_COUNT = 10


# Между запросами к Common Crawl делаем паузу.
#
# Это НЕ CBOSA.
# У Common Crawl тоже есть rate limiting,
# поэтому не будем его перегружать.
INDEX_DELAY = 1.5


HEADERS = {
    "User-Agent":
        "cbosa-portfolio-research/0.1"
}


# ============================================================
# HTTP
# ============================================================

session = requests.Session()

session.headers.update(
    HEADERS
)


# ============================================================
# HUGGING FACE
# ============================================================

def get_hf_split():
    """
    Automatycznie ustala nazwę config i split
    datasetu Hugging Face.
    """

    url = (
        f"{HF_API}/splits"
    )

    response = session.get(
        url,
        params={
            "dataset": HF_DATASET
        },
        timeout=60
    )

    response.raise_for_status()

    data = response.json()

    splits = data.get(
        "splits",
        []
    )

    if not splits:

        raise RuntimeError(
            "Hugging Face nie zwrócił splitów."
        )

    first = splits[0]

    return (
        first["config"],
        first["split"]
    )


def get_hf_row(
    config,
    split,
    offset
):
    """
    Pobiera jedną konkretną linię datasetu
    bez pobierania całych 54 GB.
    """

    url = (
        f"{HF_API}/rows"
    )

    response = session.get(
        url,
        params={
            "dataset": HF_DATASET,
            "config": config,
            "split": split,
            "offset": offset,
            "length": 1,
        },
        timeout=60
    )

    response.raise_for_status()

    data = response.json()

    rows = data.get(
        "rows",
        []
    )

    if not rows:

        raise RuntimeError(
            f"Brak row dla offset={offset}"
        )

    row = rows[0]["row"]

    total = data.get(
        "num_rows_total"
    )

    return row, total


def get_hf_samples():
    """
    Pobieramy dokumenty z różnych miejsc datasetu.

    Nie bierzemy pierwszych 10 obok siebie.

    Dzielimy cały dataset na 10 części,
    aby próbka była bardziej zróżnicowana.
    """

    print(
        "========================================"
    )

    print(
        "HUGGING FACE"
    )

    print(
        "========================================"
    )

    config, split = (
        get_hf_split()
    )

    print(
        "Config:",
        config
    )

    print(
        "Split:",
        split
    )

    # Najpierw pobieramy row 0,
    # aby poznać dokładną liczbę rekordów.

    first_row, total = get_hf_row(
        config,
        split,
        0
    )

    if total is None:

        raise RuntimeError(
            "Nie udało się odczytać liczby rekordów."
        )

    print(
        "Total rows:",
        total
    )

    # Rozkładamy offsety po całym datasecie.

    offsets = []

    if SAMPLE_COUNT == 1:

        offsets = [0]

    else:

        for i in range(
            SAMPLE_COUNT
        ):

            offset = int(
                i
                * (total - 1)
                / (SAMPLE_COUNT - 1)
            )

            offsets.append(
                offset
            )

    samples = []

    for index, offset in enumerate(
        offsets,
        start=1
    ):

        if offset == 0:

            row = first_row

        else:

            row, _ = get_hf_row(
                config,
                split,
                offset
            )

        judgment_id = row.get(
            "judgment_id"
        )

        docket_number = row.get(
            "docket_number"
        )

        judgment_date = row.get(
            "judgment_date"
        )

        if not judgment_id:

            print(
                "BRAK judgment_id:",
                offset
            )

            continue

        doc_id = (
            judgment_id
            .rstrip("/")
            .split("/")[-1]
        )

        sample = {
            "offset":
                offset,

            "doc_id":
                doc_id,

            "judgment_id":
                judgment_id,

            "docket_number":
                docket_number,

            "judgment_date":
                str(
                    judgment_date
                ),
        }

        samples.append(
            sample
        )

        print(
            f"[{index}/{SAMPLE_COUNT}]"
        )

        print(
            "  offset:",
            offset
        )

        print(
            "  doc_id:",
            doc_id
        )

        print(
            "  sygnatura:",
            docket_number
        )

        print(
            "  data:",
            judgment_date
        )

    return samples


# ============================================================
# COMMON CRAWL
# ============================================================

def get_commoncrawl_collections():
    """
    Pobiera oficjalną listę indeksów Common Crawl.
    """

    response = session.get(
        CC_COLLECTIONS_URL,
        timeout=60
    )

    response.raise_for_status()

    return response.json()


def choose_test_collections(
    collections
):
    """
    Nie sprawdzamy wszystkich indeksów Common Crawl.

    Do szybkiego testu:
    - wszystkie dostępne indeksy 2026,
    - po jednym najnowszym indeksie
      z każdego roku 2014-2025.

    To nadal NIE jest pełne pokrycie Common Crawl.
    Jest to tylko proof of concept.
    """

    selected = []

    selected_ids = set()

    # --------------------------------------------
    # Wszystkie crawle 2026
    # --------------------------------------------

    for collection in collections:

        collection_id = (
            collection["id"]
        )

        if collection_id.startswith(
            "CC-MAIN-2026-"
        ):

            selected.append(
                collection
            )

            selected_ids.add(
                collection_id
            )

    # --------------------------------------------
    # Jeden crawl na rok.
    #
    # collinfo jest ułożone od najnowszego,
    # więc pierwszy znaleziony jest najnowszy
    # w danym roku.
    # --------------------------------------------

    for year in range(
        2025,
        2013,
        -1
    ):

        prefix = (
            f"CC-MAIN-{year}-"
        )

        for collection in collections:

            collection_id = (
                collection["id"]
            )

            if (
                collection_id.startswith(
                    prefix
                )
                and
                collection_id
                not in selected_ids
            ):

                selected.append(
                    collection
                )

                selected_ids.add(
                    collection_id
                )

                break

    return selected


def query_commoncrawl(
    collection,
    doc_id
):
    """
    Szuka dokładnego /doc/{ID}
    w jednym indeksie Common Crawl.
    """

    api_url = (
        collection["cdx-api"]
    )

    target_url = (
        "orzeczenia.nsa.gov.pl"
        f"/doc/{doc_id}"
    )

    params = {
        "url": target_url,
        "output": "json",
    }

    # Maksymalnie dwie próby,
    # jeśli Common Crawl odpowie 429/503.

    for attempt in range(2):

        try:

            response = session.get(
                api_url,
                params=params,
                timeout=60
            )

        except requests.RequestException as error:

            print(
                "    CC connection error:",
                error
            )

            return []

        # Brak capture.

        if response.status_code == 404:

            return []

        # Rate limiting / temporary overload.

        if response.status_code in (
            429,
            503
        ):

            wait = (
                20
                * (attempt + 1)
            )

            print(
                f"    Common Crawl {response.status_code}."
            )

            print(
                f"    Czekam {wait} sek..."
            )

            time.sleep(
                wait
            )

            continue

        response.raise_for_status()

        text = (
            response.text.strip()
        )

        if not text:

            return []

        results = []

        for line in text.splitlines():

            line = line.strip()

            if not line:

                continue

            try:

                item = json.loads(
                    line
                )

            except json.JSONDecodeError:

                continue

            # Interesuje nas normalny HTTP 200.

            status = str(
                item.get(
                    "status",
                    ""
                )
            )

            if status == "200":

                results.append(
                    item
                )

        return results

    return []


# ============================================================
# WARC -> HTML
# ============================================================

def download_warc_html(
    capture
):
    """
    Pobiera wyłącznie fragment WARC
    zawierający jedną zapisaną stronę.

    Nie pobiera całego ogromnego pliku WARC.
    """

    filename = capture.get(
        "filename"
    )

    offset = capture.get(
        "offset"
    )

    length = capture.get(
        "length"
    )

    if (
        filename is None
        or offset is None
        or length is None
    ):

        raise RuntimeError(
            "Capture nie posiada "
            "filename/offset/length."
        )

    offset = int(
        offset
    )

    length = int(
        length
    )

    end = (
        offset
        + length
        - 1
    )

    url = (
        CC_DATA_BASE
        + filename
    )

    print(
        "\nPobieram WARC record..."
    )

    print(
        "WARC:",
        filename
    )

    print(
        "Offset:",
        offset
    )

    print(
        "Length:",
        length
    )

    response = session.get(
        url,
        headers={
            "Range":
                f"bytes={offset}-{end}"
        },
        timeout=120
    )

    if response.status_code not in (
        200,
        206
    ):

        raise RuntimeError(
            "Błąd pobierania WARC: "
            f"HTTP {response.status_code}"
        )

    stream = io.BytesIO(
        response.content
    )

    for record in ArchiveIterator(
        stream
    ):

        if record.rec_type != "response":

            continue

        payload = (
            record
            .content_stream()
            .read()
        )

        if not payload:

            continue

        # Spróbujemy ustalić charset.

        charset = "utf-8"

        if record.http_headers:

            content_type = (
                record.http_headers
                .get_header(
                    "Content-Type"
                )
                or ""
            )

            match = re.search(
                r"charset=([^\s;]+)",
                content_type,
                flags=re.IGNORECASE
            )

            if match:

                charset = (
                    match.group(1)
                    .strip("\"'")
                )

        try:

            html_text = payload.decode(
                charset,
                errors="replace"
            )

        except LookupError:

            html_text = payload.decode(
                "utf-8",
                errors="replace"
            )

        # Zachowujemy oryginalne bytes.

        with open(
            "cc_sample.html",
            "wb"
        ) as file:

            file.write(
                payload
            )

        return html_text

    raise RuntimeError(
        "Nie znaleziono response record w WARC."
    )


# ============================================================
# PARSER
# ============================================================

def test_existing_parser(
    html_text
):
    """
    Sprawdza czy nasz obecny parser CBOSA
    potrafi odczytać HTML z Common Crawl.
    """

    print(
        "\n========================================"
    )

    print(
        "TEST NASZEGO PARSERA"
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
            "Nie udało się importować "
            "parse_document.py:"
        )

        print(
            type(error).__name__,
            error
        )

        return

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
# MAIN
# ============================================================

def main():

    print(
        "========================================"
    )

    print(
        "HF + COMMON CRAWL PROBE"
    )

    print(
        "========================================"
    )

    # --------------------------------------------------------
    # 1. Hugging Face sample
    # --------------------------------------------------------

    samples = (
        get_hf_samples()
    )

    print(
        "\n========================================"
    )

    print(
        "COMMON CRAWL COLLECTIONS"
    )

    print(
        "========================================"
    )

    collections = (
        get_commoncrawl_collections()
    )

    test_collections = (
        choose_test_collections(
            collections
        )
    )

    print(
        "Testowanych indeksów:",
        len(test_collections)
    )

    for collection in test_collections:

        print(
            collection["id"],
            "-",
            collection["name"]
        )

    # --------------------------------------------------------
    # 2. Search Common Crawl
    # --------------------------------------------------------

    print(
        "\n========================================"
    )

    print(
        "SZUKAM DOC_ID W COMMON CRAWL"
    )

    print(
        "========================================"
    )

    found_samples = []

    first_capture = None

    for sample_index, sample in enumerate(
        samples,
        start=1
    ):

        doc_id = (
            sample["doc_id"]
        )

        print(
            "\n----------------------------------------"
        )

        print(
            f"DOC {sample_index}/{len(samples)}"
        )

        print(
            "doc_id:",
            doc_id
        )

        print(
            "sygnatura:",
            sample.get(
                "docket_number"
            )
        )

        sample_found = False

        for collection in test_collections:

            collection_id = (
                collection["id"]
            )

            print(
                "  sprawdzam:",
                collection_id
            )

            hits = query_commoncrawl(
                collection,
                doc_id
            )

            # Zawsze zwalniamy między
            # zapytaniami do indeksu.

            time.sleep(
                INDEX_DELAY
            )

            if hits:

                hit = hits[0]

                print(
                    "  >>> HIT:",
                    collection_id
                )

                print(
                    "      timestamp:",
                    hit.get(
                        "timestamp"
                    )
                )

                print(
                    "      mime:",
                    hit.get(
                        "mime"
                    )
                )

                print(
                    "      length:",
                    hit.get(
                        "length"
                    )
                )

                found_samples.append(
                    {
                        "sample":
                            sample,

                        "collection":
                            collection_id,

                        "capture":
                            hit,
                    }
                )

                if first_capture is None:

                    first_capture = hit

                sample_found = True

                # Jeden capture wystarczy
                # do tego dokumentu.

                break

        if not sample_found:

            print(
                "  >>> MISS "
                "w testowanych indeksach"
            )

    # --------------------------------------------------------
    # 3. Summary
    # --------------------------------------------------------

    total_samples = len(
        samples
    )

    found_count = len(
        found_samples
    )

    ratio = (
        found_count
        / total_samples
        * 100
        if total_samples
        else 0
    )

    print(
        "\n========================================"
    )

    print(
        "WYNIK PROBE"
    )

    print(
        "========================================"
    )

    print(
        "Dokumentów testowych:",
        total_samples
    )

    print(
        "Znalezionych w CC:",
        found_count
    )

    print(
        "Nieznalezionych:",
        total_samples
        - found_count
    )

    print(
        f"Hit rate: {ratio:.1f}%"
    )

    # Zachowujemy wynik.

    with open(
        "cc_probe_results.json",
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            found_samples,
            file,
            ensure_ascii=False,
            indent=2
        )

    print(
        "Zapisano:"
        " cc_probe_results.json"
    )

    # --------------------------------------------------------
    # 4. Download actual HTML
    # --------------------------------------------------------

    if first_capture is None:

        print(
            "\nNie znaleziono żadnego capture."
        )

        print(
            "Na tym etapie nie pobieram WARC."
        )

        return

    print(
        "\n========================================"
    )

    print(
        "POBIERANIE HTML Z COMMON CRAWL"
    )

    print(
        "========================================"
    )

    html_text = download_warc_html(
        first_capture
    )

    print(
        "HTML bytes/text length:",
        len(html_text)
    )

    print(
        "Zapisano: cc_sample.html"
    )

    # --------------------------------------------------------
    # 5. Test parsera
    # --------------------------------------------------------

    test_existing_parser(
        html_text
    )


if __name__ == "__main__":
    main()
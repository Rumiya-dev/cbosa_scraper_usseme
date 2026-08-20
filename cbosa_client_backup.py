import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://orzeczenia.nsa.gov.pl"

QUERY_URL = f"{BASE_URL}/cbo/query"
SEARCH_URL = f"{BASE_URL}/cbo/search"

MAX_RETRIES = 5


# ============================================================
# SESJA
# ============================================================

session = requests.Session()

session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/151.0.0.0 Safari/537.36"
    ),

    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),

    "Accept-Language": (
        "pl-PL,pl;q=0.9,en;q=0.8"
    ),

    "DNT": "1",

    "Upgrade-Insecure-Requests": "1",

    "Sec-Fetch-Dest": "document",

    "Sec-Fetch-Mode": "navigate",

    "Sec-Fetch-Site": "same-origin",

    "Sec-Fetch-User": "?1",
})


# ============================================================
# REQUEST + RETRY
# ============================================================

def request_with_retry(method, url, **kwargs):
    """
    Wysyła żądanie HTTP.

    Jeśli serwer zerwie połączenie,
    próbuje ponownie z coraz dłuższą przerwą.
    """

    for attempt in range(
        1,
        MAX_RETRIES + 1
    ):

        try:

            print(
                f"Próba {attempt}/{MAX_RETRIES}: "
                f"{method.upper()} {url}"
            )

            response = session.request(
                method=method,
                url=url,
                timeout=60,
                **kwargs,
            )

            print(
                "Status:",
                response.status_code
            )

            if response.status_code == 200:
                return response

        except requests.RequestException as error:

            print(
                "Błąd połączenia:",
                type(error).__name__,
                error
            )

        if attempt < MAX_RETRIES:

            wait_time = (
                5 * (2 ** (attempt - 1))
            )

            print(
                f"Czekam {wait_time} sek..."
            )

            time.sleep(
                wait_time
            )

    raise RuntimeError(
        f"Nie udało się pobrać: {url}"
    )


# ============================================================
# OTWARCIE CBOSA
# ============================================================

def open_cbosa():
    """
    Otwiera formularz wyszukiwarki.

    Jest to potrzebne m.in. po to,
    aby uzyskać cookies / JSESSIONID.
    """

    response = request_with_retry(
        "GET",
        QUERY_URL,
    )

    return response


# ============================================================
# SEARCH
# ============================================================

def search_documents(
    date_from,
    date_to
):
    """
    Wykonuje wyszukiwanie według dat.

    Zwraca HTML pierwszej strony wyników.
    """

    payload = {
        "wszystkieSlowa": "",
        "wystepowanie": "gdziekolwiek",
        "odmiana": "on",
        "sygnatura": "",
        "sad": "dowolny",
        "rodzaj": "dowolny",
        "symbole": "",
        "odDaty": date_from,
        "doDaty": date_to,
        "sedziowie": "",
        "funkcja": "dowolna",
        "rodzaj_organu": "",
        "hasla": "",
        "akty": "",
        "przepisy": "",
        "publikacje": "",
        "glosy": "",
        "submit": "Szukaj",
    }

    response = request_with_retry(
        "POST",
        SEARCH_URL,

        data=payload,

        headers={
            "Referer":
                f"{BASE_URL}/pl/cbo/query",

            "Origin":
                BASE_URL,
        },
    )

    return response.content


# ============================================================
# INFORMACJE O WYSZUKIWANIU
# ============================================================

def extract_search_info(html):
    """
    Czyta np.:

    Znaleziono 1126 orzeczeń, Str. 1 z 113

    i zwraca liczby.
    """

    soup = BeautifulSoup(
        html,
        "lxml"
    )

    text = soup.get_text(
        " ",
        strip=True
    )

    pattern = (
        r"Znaleziono\s+"
        r"(\d+)\s+orzeczeń"
        r",\s*Str\.\s*"
        r"(\d+)\s+z\s+(\d+)"
    )

    match = re.search(
        pattern,
        text
    )

    if not match:

        raise RuntimeError(
            "Nie znaleziono informacji "
            "o liczbie stron."
        )

    return {
        "total_documents":
            int(match.group(1)),

        "current_page":
            int(match.group(2)),

        "total_pages":
            int(match.group(3)),
    }


# ============================================================
# LINKI DO GŁÓWNYCH ORZECZEŃ
# ============================================================

def extract_document_links(html):
    """
    Pobiera tylko główne wyniki.

    Pomija orzeczenia powiązane.
    """

    soup = BeautifulSoup(
        html,
        "lxml"
    )

    links = []

    result_tables = soup.select(
        "#res-div > table.info-list"
    )

    for table in result_tables:

        link = table.select_one(
            "tr.niezaznaczona "
            "td.info-list-value "
            'a[href^="/doc/"]'
        )

        if link is None:
            continue

        href = link.get(
            "href"
        )

        if not href:
            continue

        doc_id = (
            href.rstrip("/")
            .split("/")[-1]
        )

        if "." in doc_id:
            continue

        full_url = urljoin(
            BASE_URL,
            href
        )

        links.append(
            full_url
        )

    return links


# ============================================================
# KONKRETNA STRONA
# ============================================================

def download_result_page(
    page_number
):
    """
    Pobiera kolejną stronę wyników
    poprzedniego wyszukiwania.
    """

    url = (
        f"{BASE_URL}/cbo/find"
        f"?p={page_number}"
    )

    response = request_with_retry(
        "GET",
        url,

        headers={
            "Referer":
                SEARCH_URL
        },
    )

    return response.content
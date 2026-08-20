import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


# ============================================================
# USTAWIENIA
# ============================================================

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

    "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",

    "DNT": "1",

    "Upgrade-Insecure-Requests": "1",

    "Sec-Fetch-Dest": "document",

    "Sec-Fetch-Mode": "navigate",

    "Sec-Fetch-Site": "same-origin",

    "Sec-Fetch-User": "?1",
})


# ============================================================
# REQUEST Z RETRY
# ============================================================

def request_with_retry(method, url, **kwargs):
    """
    Wysyła zapytanie do serwera.

    Jeżeli serwer zerwie połączenie,
    funkcja czeka i próbuje ponownie.
    """

    for attempt in range(1, MAX_RETRIES + 1):

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
                "Błąd:",
                type(error).__name__,
                error
            )

        if attempt < MAX_RETRIES:

            wait_time = 5 * (2 ** (attempt - 1))

            print(
                f"Czekam {wait_time} sek..."
            )

            time.sleep(wait_time)

    raise RuntimeError(
        f"Nie udało się pobrać: {url}"
    )


# ============================================================
# OTWARCIE CBOSA
# ============================================================

def open_cbosa():

    print("\n========================================")
    print("1. OTWIERAM CBOSA")
    print("========================================")

    response = request_with_retry(
        "GET",
        QUERY_URL
    )

    print("Formularz OK.")

    return response


# ============================================================
# WYSZUKIWANIE
# ============================================================

def search_documents(date_from, date_to):

    print("\n========================================")
    print("2. WYSZUKUJĘ")
    print("========================================")

    print(
        f"Data: {date_from} -> {date_to}"
    )

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
# INFORMACJA O LICZBIE STRON
# ============================================================

def extract_search_info(html):
    """
    Z tekstu:

        Znaleziono 1126 orzeczeń, Str. 1 z 113

    pobiera:

        total_documents = 1126
        current_page = 1
        total_pages = 113
    """

    soup = BeautifulSoup(
        html,
        "lxml"
    )

    page_text = soup.get_text(
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
        page_text
    )

    if not match:

        raise RuntimeError(
            "Nie udało się odczytać "
            "liczby wyników i stron."
        )

    total_documents = int(
        match.group(1)
    )

    current_page = int(
        match.group(2)
    )

    total_pages = int(
        match.group(3)
    )

    return {
        "total_documents":
            total_documents,

        "current_page":
            current_page,

        "total_pages":
            total_pages,
    }


# ============================================================
# GŁÓWNE LINKI DO ORZECZEŃ
# ============================================================

def extract_document_links(html):
    """
    Pobiera TYLKO główne wyniki wyszukiwania.

    Nie pobiera orzeczeń powiązanych znajdujących się
    w <span class="powiazane">.
    """

    soup = BeautifulSoup(
        html,
        "lxml"
    )

    links = []

    # Każde orzeczenie z listy znajduje się
    # w osobnej tabeli .info-list.
    result_tables = soup.select(
        "#res-div > table.info-list"
    )

    for table in result_tables:

        # Szukamy tylko PIERWSZEGO głównego linku
        # /doc/... w tabeli.
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

        document_id = (
            href.rstrip("/")
            .split("/")[-1]
        )

        # Nie bierzemy np. .rtf.
        if "." in document_id:
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
# POBRANIE STRONY WYNIKÓW
# ============================================================

def download_result_page(page_number):

    url = (
        f"{BASE_URL}/cbo/find"
        f"?p={page_number}"
    )

    print(
        f"\nPobieram stronę {page_number}"
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


# ============================================================
# WYŚWIETLANIE LINKÓW
# ============================================================

def show_page_info(
    page_number,
    html
):

    links = extract_document_links(
        html
    )

    print("\n========================================")
    print(f"STRONA {page_number}")
    print("========================================")

    print(
        "Liczba głównych orzeczeń:",
        len(links)
    )

    for number, url in enumerate(
        links,
        start=1
    ):

        document_id = (
            url.rstrip("/")
            .split("/")[-1]
        )

        print(
            f"{number}. {document_id}"
        )

    return links


# ============================================================
# MAIN
# ============================================================

def main():

    print("========================================")
    print("TEST PAGINACJI CBOSA - WERSJA 2")
    print("========================================")

    # --------------------------------------------------------
    # 1. Otwieramy stronę.
    # --------------------------------------------------------

    open_cbosa()

    time.sleep(2)

    # --------------------------------------------------------
    # 2. Wysyłamy wyszukiwanie.
    # --------------------------------------------------------

    page_1_html = search_documents(
        "2026-08-01",
        "2026-08-10"
    )

    # --------------------------------------------------------
    # 3. Automatycznie odczytujemy liczbę stron.
    # --------------------------------------------------------

    info = extract_search_info(
        page_1_html
    )

    print("\n========================================")
    print("INFORMACJE O WYSZUKIWANIU")
    print("========================================")

    print(
        "Liczba wszystkich orzeczeń:",
        info["total_documents"]
    )

    print(
        "Aktualna strona:",
        info["current_page"]
    )

    print(
        "Liczba wszystkich stron:",
        info["total_pages"]
    )

    # --------------------------------------------------------
    # 4. Strona 1.
    # --------------------------------------------------------

    page_1_links = show_page_info(
        1,
        page_1_html
    )

    # --------------------------------------------------------
    # 5. Strona 2.
    # --------------------------------------------------------

    time.sleep(5)

    page_2_html = download_result_page(
        2
    )

    page_2_links = show_page_info(
        2,
        page_2_html
    )

    # --------------------------------------------------------
    # 6. Strona 3.
    # --------------------------------------------------------

    time.sleep(5)

    page_3_html = download_result_page(
        3
    )

    page_3_links = show_page_info(
        3,
        page_3_html
    )

    # --------------------------------------------------------
    # 7. Łączymy wyniki.
    # --------------------------------------------------------

    all_links = (
        page_1_links
        + page_2_links
        + page_3_links
    )

    unique_links = list(
        dict.fromkeys(
            all_links
        )
    )

    duplicates = (
        len(all_links)
        - len(unique_links)
    )

    print("\n========================================")
    print("PODSUMOWANIE")
    print("========================================")

    print(
        "Strona 1:",
        len(page_1_links)
    )

    print(
        "Strona 2:",
        len(page_2_links)
    )

    print(
        "Strona 3:",
        len(page_3_links)
    )

    print(
        "Razem:",
        len(all_links)
    )

    print(
        "Unikalnych:",
        len(unique_links)
    )

    print(
        "Duplikaty:",
        duplicates
    )


if __name__ == "__main__":
    main()
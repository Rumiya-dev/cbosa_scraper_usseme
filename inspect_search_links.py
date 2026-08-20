import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin


BASE_URL = "https://orzeczenia.nsa.gov.pl"
QUERY_URL = f"{BASE_URL}/cbo/query"
SEARCH_URL = f"{BASE_URL}/cbo/search"

MAX_RETRIES = 5


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
})


def request_with_retry(method, url, **kwargs):

    for attempt in range(1, MAX_RETRIES + 1):

        try:

            print(
                f"Próba {attempt}/{MAX_RETRIES}: "
                f"{method.upper()} {url}"
            )

            response = session.request(
                method,
                url,
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


def open_search():

    print("\n1. Otwieram formularz...")

    request_with_retry(
        "GET",
        QUERY_URL
    )

    time.sleep(2)

    payload = {
        "wszystkieSlowa": "",
        "wystepowanie": "gdziekolwiek",
        "odmiana": "on",
        "sygnatura": "",
        "sad": "dowolny",
        "rodzaj": "dowolny",
        "symbole": "",
        "odDaty": "2026-08-01",
        "doDaty": "2026-08-10",
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

    print("\n2. Wysyłam wyszukiwanie...")

    request_with_retry(
        "POST",
        SEARCH_URL,
        data=payload,
        headers={
            "Referer": f"{BASE_URL}/pl/cbo/query",
            "Origin": BASE_URL,
        },
    )


def get_page(page_number):

    url = (
        f"{BASE_URL}/cbo/find"
        f"?p={page_number}"
    )

    print(
        f"\n3. Pobieram stronę {page_number}..."
    )

    response = request_with_retry(
        "GET",
        url,
        headers={
            "Referer": SEARCH_URL,
        },
    )

    return response.content


def inspect_links(html):

    soup = BeautifulSoup(
        html,
        "lxml"
    )

    print(
        "\n========================================"
    )
    print(
        "WSZYSTKIE LINKI /doc/"
    )
    print(
        "========================================"
    )

    number = 0

    for link in soup.find_all(
        "a",
        href=True
    ):

        href = link["href"]

        if not href.startswith("/doc/"):
            continue

        document_id = (
            href.rstrip("/")
            .split("/")[-1]
        )

        if "." in document_id:
            continue

        number += 1

        text = link.get_text(
            " ",
            strip=True
        )

        print(
            f"\nLINK #{number}"
        )

        print(
            "ID:",
            document_id
        )

        print(
            "TEKST:",
            repr(text)
        )

        print(
            "CLASS:",
            link.get("class")
        )

        print(
            "ID HTML:",
            link.get("id")
        )

        parent = link.parent

        print(
            "PARENT TAG:",
            parent.name
            if parent
            else None
        )

        print(
            "PARENT CLASS:",
            parent.get("class")
            if parent
            else None
        )

        if parent:

            parent_text = parent.get_text(
                " ",
                strip=True
            )

            print(
                "PARENT TEXT:",
                repr(
                    parent_text[:300]
                )
            )

        print(
            "HREF:",
            urljoin(
                BASE_URL,
                href
            )
        )

    print(
        "\n========================================"
    )

    print(
        "RAZEM:",
        number
    )


def main():

    open_search()

    time.sleep(3)

    # Нам особенно интересна страница 2,
    # потому что там предыдущий код нашёл 12 ссылок.
    html = get_page(2)

    with open(
        "debug_page_2.html",
        "wb"
    ) as file:

        file.write(
            html
        )

    print(
        "\nZapisano: debug_page_2.html"
    )

    inspect_links(
        html
    )


if __name__ == "__main__":
    main()
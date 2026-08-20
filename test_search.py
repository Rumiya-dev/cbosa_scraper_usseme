import time
import requests
from bs4 import BeautifulSoup


BASE_URL = "https://orzeczenia.nsa.gov.pl"
QUERY_URL = f"{BASE_URL}/cbo/query"
SEARCH_URL = f"{BASE_URL}/cbo/search"


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

    max_attempts = 5

    for attempt in range(1, max_attempts + 1):

        try:
            print(
                f"Próba {attempt}/{max_attempts}: "
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

            print(
                "Niepoprawny status. "
                "Ponawiam..."
            )

        except requests.RequestException as e:

            print(
                "Błąd:",
                type(e).__name__,
                e
            )

        if attempt < max_attempts:

            wait = attempt * 3

            print(
                f"Czekam {wait} sek..."
            )

            time.sleep(wait)

    raise RuntimeError(
        "Nie udało się wykonać żądania."
    )


def main():

    print(
        "\n1. Otwieram formularz CBOSA..."
    )

    response = request_with_retry(
        "GET",
        QUERY_URL,
    )

    print(
        "Cookies:",
        session.cookies.get_dict()
    )

    time.sleep(2)

    print(
        "\n2. Wysyłam formularz wyszukiwania..."
    )

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

    response = request_with_retry(
        "POST",
        SEARCH_URL,
        data=payload,
        headers={
            "Referer": (
                f"{BASE_URL}/pl/cbo/query"
            ),
            "Origin": BASE_URL,
        },
    )

    print(
        "\nRozmiar strony:",
        len(response.content),
        "bytes"
    )

    with open(
        "test_search.html",
        "wb"
    ) as file:
        file.write(
            response.content
        )

    print(
        "Zapisano: test_search.html"
    )

    print(
        "\n3. Szukam linków do orzeczeń..."
    )

    soup = BeautifulSoup(
        response.content,
        "lxml"
    )

    links = []

    for link in soup.find_all(
        "a",
        href=True
    ):

        href = link["href"]

        if href.startswith("/doc/"):

            # Odrzucamy np. pliki .rtf,
            # jeżeli kiedyś pojawią się na liście.
            if "." not in href.split("/")[-1]:

                links.append(
                    href
                )

    # Usuwamy ewentualne duplikaty,
    # zachowując kolejność.
    links = list(
        dict.fromkeys(links)
    )

    print(
        "Znaleziono linków:",
        len(links)
    )

    print(
        "\nPierwsze linki:"
    )

    for link in links[:10]:

        print(
            BASE_URL + link
        )


if __name__ == "__main__":
    main()
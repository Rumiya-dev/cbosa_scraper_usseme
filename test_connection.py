import time
import requests


BASE_URL = "https://orzeczenia.nsa.gov.pl"

QUERY_URL = f"{BASE_URL}/cbo/query"

DOC_URL = f"{BASE_URL}/doc/C98C7817E2"

SEARCH_REFERER = f"{BASE_URL}/pl/cbo/search"


session = requests.Session()

session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/151.0.0.0 Safari/537.36"
    ),

    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),

    "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",

    "DNT": "1",

    "Upgrade-Insecure-Requests": "1",

    "Sec-Fetch-Dest": "document",

    "Sec-Fetch-Mode": "navigate",

    "Sec-Fetch-Site": "same-origin",

    "Sec-Fetch-User": "?1",
})


print("1. Otwieram CBOSA...")

try:

    response = session.get(
        QUERY_URL,
        timeout=30,
    )

    print("Status:", response.status_code)
    print("Rozmiar:", len(response.content))
    print("Cookies:", session.cookies.get_dict())

except Exception as e:

    print("BŁĄD QUERY:")
    print(type(e).__name__, e)

    raise SystemExit


print("\nCzekam 3 sekundy...")
time.sleep(3)


print("\n2. Otwieram orzeczenie...")

try:

    response = session.get(
        DOC_URL,

        headers={
            "Referer": SEARCH_REFERER,
        },

        timeout=60,
    )

    print("Status:", response.status_code)
    print("Final URL:", response.url)
    print("Rozmiar:", len(response.content))

    if response.status_code == 200:

        with open(
            "test_document.html",
            "wb",
        ) as file:

            file.write(response.content)

        print("\nSUKCES!")
        print("Zapisano: test_document.html")

    else:

        print("\nSerwer zwrócił:")
        print(response.status_code)


except Exception as e:

    print("\nBŁĄD DOC:")
    print(type(e).__name__)
    print(e)
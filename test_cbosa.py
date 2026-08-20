import re
import requests
from bs4 import BeautifulSoup


URL = "https://orzeczenia.nsa.gov.pl/doc/6216034CF1"


headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0 Safari/537.36"
    ),
    "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
}


def download_page(url):
    print("Pobieram:", url)

    response = requests.get(
        url,
        headers=headers,
        timeout=30,
    )

    print("HTTP status:", response.status_code)
    print("Final URL:", response.url)
    print("Rozmiar:", len(response.content), "bytes")

    response.raise_for_status()

    return response.text


def inspect_html(html):
    soup = BeautifulSoup(html, "lxml")

    print("\n========== TITLE ==========")

    if soup.title:
        print(soup.title.get_text(" ", strip=True))
    else:
        print("Brak <title>")

    print("\n========== TABLE ROWS ==========")

    rows = soup.find_all("tr")

    print("Liczba <tr>:", len(rows))

    for i, row in enumerate(rows[:50], 1):
        cells = [
            cell.get_text(" ", strip=True)
            for cell in row.find_all(["td", "th"])
        ]

        if cells:
            print(i, cells)

    print("\n========== DT / DD ==========")

    for dt in soup.find_all("dt"):
        dd = dt.find_next_sibling("dd")

        if dd:
            print(
                dt.get_text(" ", strip=True),
                "=>",
                dd.get_text(" ", strip=True)
            )

    print("\n========== INTERESTING TEXT ==========")

    keywords = [
        "Sygnatura",
        "Data orzeczenia",
        "Sąd",
        "Rodzaj orzeczenia",
        "Symbol",
        "Hasło tematyczne",
        "Sentencja",
        "Uzasadnienie",
    ]

    for keyword in keywords:

        print(f"\n--- {keyword} ---")

        elements = soup.find_all(
            string=re.compile(keyword, re.IGNORECASE)
        )

        for element in elements[:10]:
            parent = element.parent

            print(
                parent.get_text(
                    " ",
                    strip=True
                )[:1000]
            )

    print("\n========== LINKS ==========")

    links = []

    for a in soup.find_all("a", href=True):
        href = a["href"]

        if "/doc/" in href:
            links.append(href)

    for link in links[:30]:
        print(link)

    print("\nDoc links:", len(links))


def main():

    html = download_page(URL)

    with open(
        "test_document.html",
        "w",
        encoding="utf-8"
    ) as file:
        file.write(html)

    print("\nHTML zapisany do test_document.html")

    inspect_html(html)


if __name__ == "__main__":
    main()
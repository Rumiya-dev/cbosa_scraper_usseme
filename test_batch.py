import json
import os
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from parse_document import parse_document


# ============================================================
# USTAWIENIA
# ============================================================

BASE_URL = "https://orzeczenia.nsa.gov.pl"

QUERY_URL = f"{BASE_URL}/cbo/query"
SEARCH_URL = f"{BASE_URL}/cbo/search"

# В браузере переход к документу идёт как будто со страницы
# /pl/cbo/search
DOC_REFERER = f"{BASE_URL}/pl/cbo/search"

# Пока скачиваем ТОЛЬКО 3 документа.
DOCUMENT_LIMIT = 3

# Пауза между документами.
# Нам не нужно быстро нагружать нестабильный сервер.
DELAY_BETWEEN_DOCUMENTS = 6

# Сколько раз повторять запрос при ошибке.
MAX_RETRIES = 5

# Файл, куда будем записывать распарсенные результаты.
OUTPUT_FILE = "test_batch_results.txt"

# Папка для сохранения исходного HTML.
RAW_HTML_DIR = "batch_html"


# ============================================================
# SESJA HTTP
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
# FUNKCJA: request_with_retry
# ============================================================

def request_with_retry(method, url, **kwargs):
    """
    Wysyła zapytanie HTTP.

    Jeżeli serwer zerwie połączenie albo zwróci błąd,
    funkcja próbuje ponownie.

    Zwraca obiekt requests.Response.
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
                f"Status: {response.status_code}"
            )

            if response.status_code == 200:
                return response

            print(
                "Serwer nie zwrócił 200 OK."
            )

        except requests.RequestException as error:

            print(
                "Błąd połączenia:"
            )

            print(
                type(error).__name__,
                error
            )

        # Если это была последняя попытка,
        # дальше ждать уже не надо.
        if attempt == MAX_RETRIES:
            break

        # Каждая следующая пауза длиннее:
        #
        # 5 секунд
        # 10 секунд
        # 20 секунд
        # 40 секунд
        #
        wait_time = 5 * (2 ** (attempt - 1))

        print(
            f"Czekam {wait_time} sek. "
            "i próbuję ponownie..."
        )

        time.sleep(wait_time)

    raise RuntimeError(
        f"Nie udało się pobrać: {url}"
    )


# ============================================================
# FUNKCJA: open_cbosa
# ============================================================

def open_cbosa():
    """
    Otwiera formularz CBOSA.

    Robimy to przed wyszukiwaniem, żeby serwer nadał
    naszej sesji cookies, m.in. JSESSIONID.
    """

    print(
        "\n========================================"
    )

    print(
        "1. OTWIERAM CBOSA"
    )

    print(
        "========================================"
    )

    response = request_with_retry(
        "GET",
        QUERY_URL,
    )

    print(
        "Formularz otwarty."
    )

    print(
        f"Rozmiar: {len(response.content)} bytes"
    )


# ============================================================
# FUNKCJA: search_documents
# ============================================================

def search_documents(date_from, date_to):
    """
    Wysyła formularz wyszukiwarki CBOSA.

    date_from:
        np. 2026-08-01

    date_to:
        np. 2026-08-10

    Zwraca HTML pierwszej strony wyników.
    """

    print(
        "\n========================================"
    )

    print(
        "2. WYSZUKUJĘ ORZECZENIA"
    )

    print(
        "========================================"
    )

    print(
        f"Zakres dat: {date_from} -> {date_to}"
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
            "Referer": (
                f"{BASE_URL}/pl/cbo/query"
            ),

            "Origin": BASE_URL,
        },
    )

    print(
        "Wyszukiwanie zakończone."
    )

    print(
        f"Rozmiar HTML: "
        f"{len(response.content)} bytes"
    )

    return response.content


# ============================================================
# FUNKCJA: extract_document_links
# ============================================================

def extract_document_links(html):
    """
    Szuka w HTML linków typu:

        /doc/C98C7817E2

    i zamienia je na pełne adresy:

        https://orzeczenia.nsa.gov.pl/doc/C98C7817E2
    """

    print(
        "\n========================================"
    )

    print(
        "3. SZUKAM LINKÓW"
    )

    print(
        "========================================"
    )

    soup = BeautifulSoup(
        html,
        "lxml"
    )

    links = []

    for element in soup.find_all(
        "a",
        href=True
    ):

        href = element["href"]

        if not href.startswith("/doc/"):
            continue

        # Например:
        #
        # /doc/C98C7817E2
        #
        # Но ссылка:
        #
        # /doc/C98C7817E2.rtf
        #
        # нам здесь не нужна.
        document_part = href.split("/")[-1]

        if "." in document_part:
            continue

        full_url = urljoin(
            BASE_URL,
            href
        )

        links.append(
            full_url
        )

    # Убираем дубликаты,
    # но сохраняем исходный порядок.
    unique_links = list(
        dict.fromkeys(links)
    )

    print(
        f"Znaleziono: "
        f"{len(unique_links)} linków"
    )

    for number, link in enumerate(
        unique_links,
        start=1
    ):

        print(
            f"{number}. {link}"
        )

    return unique_links


# ============================================================
# FUNKCJA: get_document_id
# ============================================================

def get_document_id(url):
    """
    Z adresu:

        https://.../doc/C98C7817E2

    zwraca:

        C98C7817E2
    """

    return url.rstrip("/").split("/")[-1]


# ============================================================
# FUNKCJA: download_document
# ============================================================

def download_document(url):
    """
    Pobiera pojedyncze orzeczenie.
    """

    document_id = get_document_id(
        url
    )

    print(
        "\n----------------------------------------"
    )

    print(
        f"Pobieram dokument: {document_id}"
    )

    print(
        "----------------------------------------"
    )

    response = request_with_retry(
        "GET",
        url,

        headers={
            "Referer": DOC_REFERER,
        },
    )

    print(
        f"Pobrano: {len(response.content)} bytes"
    )

    return response.content


# ============================================================
# FUNKCJA: save_raw_html
# ============================================================

def save_raw_html(
    document_id,
    html
):
    """
    Zapisuje oryginalny HTML dokumentu.

    Dzięki temu jeśli parser kiedyś coś źle odczyta,
    mamy oryginalną stronę do sprawdzenia.
    """

    os.makedirs(
        RAW_HTML_DIR,
        exist_ok=True
    )

    filename = os.path.join(
        RAW_HTML_DIR,
        f"{document_id}.html"
    )

    with open(
        filename,
        "wb"
    ) as file:

        file.write(
            html
        )

    print(
        f"HTML zapisany: {filename}"
    )


# ============================================================
# FUNKCJA: save_result
# ============================================================

def save_result(
    document_id,
    url,
    parsed_data
):
    """
    Zapisuje jeden rekord do pliku wynikowego.

    Na razie używamy formatu JSON Lines.

    Każda linia pliku = jedno orzeczenie.
    """

    result = {
        "doc_id": document_id,
        "url": url,
        **parsed_data,
    }

    with open(
        OUTPUT_FILE,
        "a",
        encoding="utf-8"
    ) as file:

        file.write(
            json.dumps(
                result,
                ensure_ascii=False
            )
        )

        file.write(
            "\n"
        )

    print(
        f"Rekord zapisany do: "
        f"{OUTPUT_FILE}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "========================================"
    )

    print(
        "TEST CBOSA - 3 ORZECZENIA"
    )

    print(
        "========================================"
    )

    # --------------------------------------------------------
    # 1. Создаём новую чистую сессию CBOSA
    # --------------------------------------------------------

    open_cbosa()

    print(
        "\nCzekam 2 sekundy..."
    )

    time.sleep(2)

    # --------------------------------------------------------
    # 2. Выполняем поиск
    # --------------------------------------------------------

    search_html = search_documents(
        "2026-08-01",
        "2026-08-10"
    )

    # --------------------------------------------------------
    # 3. Достаём ссылки
    # --------------------------------------------------------

    links = extract_document_links(
        search_html
    )

    if not links:

        print(
            "Nie znaleziono żadnych dokumentów."
        )

        return

    # --------------------------------------------------------
    # 4. Берём только первые 3
    # --------------------------------------------------------

    links_to_download = links[
        :DOCUMENT_LIMIT
    ]

    print(
        "\n========================================"
    )

    print(
        f"POBIERAM TYLKO "
        f"{len(links_to_download)} DOKUMENTY"
    )

    print(
        "========================================"
    )

    # --------------------------------------------------------
    # Для теста удаляем старый файл результатов,
    # чтобы результаты прошлых запусков не смешивались.
    # --------------------------------------------------------

    if os.path.exists(
        OUTPUT_FILE
    ):

        os.remove(
            OUTPUT_FILE
        )

    # --------------------------------------------------------
    # 5. Скачиваем документы по одному
    # --------------------------------------------------------

    successful = 0
    failed = 0

    for index, url in enumerate(
        links_to_download,
        start=1
    ):

        document_id = get_document_id(
            url
        )

        print(
            "\n========================================"
        )

        print(
            f"DOKUMENT {index}/"
            f"{len(links_to_download)}"
        )

        print(
            f"ID: {document_id}"
        )

        print(
            "========================================"
        )

        try:

            # 5a. Скачать HTML
            html = download_document(
                url
            )

            # 5b. Сохранить оригинальный HTML
            save_raw_html(
                document_id,
                html
            )

            # 5c. Превратить bytes в текст
            html_text = html.decode(
                "utf-8",
                errors="replace"
            )

            # 5d. Передать HTML нашему парсеру
            parsed_data = parse_document(
                html_text
            )

            # 5e. Сохранить результат
            save_result(
                document_id,
                url,
                parsed_data
            )

            successful += 1

            print(
                "OK - dokument przetworzony."
            )

        except Exception as error:

            failed += 1

            print(
                "\nBŁĄD DOKUMENTU:"
            )

            print(
                document_id
            )

            print(
                type(error).__name__,
                error
            )

        # После последнего документа ждать бессмысленно.
        if index < len(
            links_to_download
        ):

            print(
                f"\nCzekam "
                f"{DELAY_BETWEEN_DOCUMENTS} "
                "sekund przed następnym "
                "dokumentem..."
            )

            time.sleep(
                DELAY_BETWEEN_DOCUMENTS
            )

    # --------------------------------------------------------
    # Итог
    # --------------------------------------------------------

    print(
        "\n========================================"
    )

    print(
        "KONIEC TESTU"
    )

    print(
        "========================================"
    )

    print(
        f"Poprawnie: {successful}"
    )

    print(
        f"Błędy: {failed}"
    )

    print(
        f"Wyniki: {OUTPUT_FILE}"
    )

    print(
        f"HTML: {RAW_HTML_DIR}"
    )


if __name__ == "__main__":
    main()
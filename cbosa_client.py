import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


# ============================================================
# ADRESY
# ============================================================

BASE_URL = "https://orzeczenia.nsa.gov.pl"

QUERY_URL = f"{BASE_URL}/cbo/query"
SEARCH_URL = f"{BASE_URL}/cbo/search"


# ============================================================
# USTAWIENIA POŁĄCZENIA
# ============================================================

# Ile krótkich prób wykonujemy,
# zanim uznamy, że CBOSA jest chwilowo niedostępna.
MAX_RETRIES = 5

# Ile razy możemy wykonać cały cykl:
#
# 5 prób
# ↓
# długa przerwa
# ↓
# nowa sesja
#
MAX_RECOVERY_CYCLES = 3

# 5 minut.
RECOVERY_COOLDOWN = 300


# ============================================================
# TWORZENIE SESJI
# ============================================================

def build_session():
    """
    Tworzy nową sesję HTTP.

    Sesja przechowuje m.in. cookies,
    np. JSESSIONID.
    """

    new_session = requests.Session()

    new_session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/151.0.0.0 Safari/537.36"
        ),

        "Accept": (
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,"
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

    return new_session


# Pierwsza sesja programu.
session = build_session()


# ============================================================
# RESET SESJI
# ============================================================

def reset_session():
    """
    Usuwa starą sesję i tworzy nową.

    Jest to przydatne, gdy serwer przez dłuższy czas
    przestaje odpowiadać.
    """

    global session

    try:
        session.close()
    except Exception:
        pass

    session = build_session()

    print(
        "Utworzono nową sesję HTTP."
    )


# ============================================================
# ROZGRZANIE NOWEJ SESJI
# ============================================================

def warm_up_session():
    """
    Po utworzeniu nowej sesji próbujemy wejść
    na formularz CBOSA i uzyskać nowe cookies.

    Ta funkcja nie robi pełnego mechanizmu retry,
    żeby nie tworzyć pętli wewnątrz pętli.
    """

    print(
        "Próbuję ponownie otworzyć CBOSA..."
    )

    try:

        response = session.get(
            QUERY_URL,
            timeout=60,
        )

        print(
            "Warm-up status:",
            response.status_code
        )

        return (
            response.status_code == 200
        )

    except requests.RequestException as error:

        print(
            "Warm-up nieudany:",
            type(error).__name__,
            error
        )

        return False


# ============================================================
# REQUEST + RETRY + RECOVERY
# ============================================================

def request_with_retry(
    method,
    url,
    **kwargs
):
    """
    Główna funkcja do komunikacji z CBOSA.

    Poziom 1:
        krótkie retry z exponential backoff.

    Poziom 2:
        jeśli wszystkie krótkie retry zawiodą,
        czekamy 5 minut, tworzymy nową sesję
        i próbujemy ponownie.
    """

    last_error = None

    # --------------------------------------------------------
    # DŁUGIE CYKLE RECOVERY
    # --------------------------------------------------------

    for recovery_cycle in range(
        1,
        MAX_RECOVERY_CYCLES + 1
    ):

        print(
            f"\nRecovery cycle "
            f"{recovery_cycle}/"
            f"{MAX_RECOVERY_CYCLES}"
        )

        # ----------------------------------------------------
        # KRÓTKIE RETRY
        # ----------------------------------------------------

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

                # --------------------------------------------
                # SUKCES
                # --------------------------------------------

                if response.status_code == 200:

                    return response

                # --------------------------------------------
                # TYMCZASOWE BŁĘDY SERWERA
                # --------------------------------------------

                if response.status_code in {
                    429,
                    500,
                    502,
                    503,
                    504,
                }:

                    last_error = RuntimeError(
                        f"HTTP "
                        f"{response.status_code}"
                    )

                    print(
                        "Tymczasowy błąd serwera."
                    )

                else:

                    # Np. 404 nie ma sensu próbować
                    # dziesiątki razy.
                    raise RuntimeError(
                        f"Nieoczekiwany HTTP "
                        f"{response.status_code}: "
                        f"{url}"
                    )

            except requests.RequestException as error:

                last_error = error

                print(
                    "Błąd połączenia:",
                    type(error).__name__,
                    error
                )

            # -----------------------------------------------
            # BACKOFF
            # -----------------------------------------------

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

        # ====================================================
        # 5 KRÓTKICH PRÓB SIĘ NIE UDAŁO
        # ====================================================

        print(
            "\n========================================"
        )

        print(
            "CBOSA CHWILOWO NIEDOSTĘPNA"
        )

        print(
            "========================================"
        )

        # Если это последний длинный цикл,
        # дальше уже не ждём.
        if (
            recovery_cycle
            == MAX_RECOVERY_CYCLES
        ):

            break

        print(
            f"Czekam {RECOVERY_COOLDOWN} sekund "
            "(5 minut)..."
        )

        time.sleep(
            RECOVERY_COOLDOWN
        )

        # ----------------------------------------------------
        # Старая сессия удаляется.
        # ----------------------------------------------------

        reset_session()

        # ----------------------------------------------------
        # Получаем новые cookies.
        # ----------------------------------------------------

        warm_up_session()

    # ========================================================
    # ВСЕ ЦИКЛЫ ИСЧЕРПАНЫ
    # ========================================================

    raise RuntimeError(
        "CBOSA pozostaje niedostępna "
        "po wszystkich próbach. "
        f"Ostatni błąd: {last_error}"
    )


# ============================================================
# OTWARCIE CBOSA
# ============================================================

def open_cbosa():

    return request_with_retry(
        "GET",
        QUERY_URL,
    )


# ============================================================
# SEARCH
# ============================================================

def search_documents(
    date_from,
    date_to
):

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
# KOLEJNA STRONA WYNIKÓW
# ============================================================

def download_result_page(
    page_number
):

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
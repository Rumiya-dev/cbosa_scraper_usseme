from bs4 import BeautifulSoup
import json
import re


FILE = "test_document.html"


def clean_text(element):
    if element is None:
        return None

    return element.get_text(" ", strip=True)


def inner_html(element):
    if element is None:
        return None

    return element.decode_contents().strip()


def extract_metadata(soup):
    metadata = {}

    rows = soup.select(
        "table.info-list tr.niezaznaczona"
    )

    for row in rows:

        label = row.select_one(
            "td.info-list-label .lista-label"
        )

        value = row.select_one(
            "td.info-list-value"
        )

        if not label or not value:
            continue

        key = clean_text(label)

        # Data orzeczenia ma dodatkowo informację
        # typu "orzeczenie nieprawomocne".
        # Bierzemy tylko właściwą datę.
        if key == "Data orzeczenia":

            first_td = value.find("td")

            if first_td:
                value_text = clean_text(first_td)
            else:
                value_text = clean_text(value)

        else:
            value_text = clean_text(value)

        metadata[key] = value_text

    return metadata


def extract_section_html(soup, section_name):

    labels = soup.select(
        "div.lista-label"
    )

    for label in labels:

        if (
            clean_text(label).casefold()
            == section_name.casefold()
        ):

            content = label.find_next_sibling(
                "span",
                class_="info-list-value-uzasadnienie"
            )

            return inner_html(content)

    return None


def parse_document(html):

    soup = BeautifulSoup(
        html,
        "lxml"
    )

    # Nagłówek:
    # I SAB/Wr 395/26 - Postanowienie WSA we Wrocławiu

    header = soup.select_one(
        ".war_header"
    )

    header_text = clean_text(header)

    sygnatura = None
    rodzaj_i_sad = None

    if header_text:

        match = re.match(
            r"^(.*?)\s+-\s+(.*)$",
            header_text
        )

        if match:

            sygnatura = (
                match.group(1).strip()
            )

            rodzaj_i_sad = (
                match.group(2).strip()
            )

    metadata = extract_metadata(
        soup
    )

    result = {

        "tytul": header_text,

        "sygnatura": sygnatura,

        "rodzaj_i_sad":
            rodzaj_i_sad,

        "data_orzeczenia":
            metadata.get(
                "Data orzeczenia"
            ),

        "data_wplywu":
            metadata.get(
                "Data wpływu"
            ),

        "sad":
            metadata.get(
                "Sąd"
            ),

        "sedziowie":
            metadata.get(
                "Sędziowie"
            ),

        "symbol_z_opisem":
            metadata.get(
                "Symbol z opisem"
            ),

        "hasla_tematyczne":
            metadata.get(
                "Hasła tematyczne"
            ),

        "skarzony_organ":
            metadata.get(
                "Skarżony organ"
            ),

        "tresc_wyniku":
            metadata.get(
                "Treść wyniku"
            ),

        "powolane_przepisy":
            metadata.get(
                "Powołane przepisy"
            ),

        "sentencja_html":
            extract_section_html(
                soup,
                "Sentencja"
            ),

        "uzasadnienie_html":
            extract_section_html(
                soup,
                "Uzasadnienie"
            ),
    }

    return result


def main():

    with open(
        FILE,
        "r",
        encoding="utf-8"
    ) as file:

        html = file.read()

    document = parse_document(
        html
    )

    print(
        json.dumps(
            document,
            ensure_ascii=False,
            indent=2
        )
    )


if __name__ == "__main__":
    main()
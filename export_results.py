import json
import sqlite3

from database import (
    DATABASE_FILE,
    create_database,
)


OUTPUT_FILE = "export_results.jsonl"


def main():

    print(
        "========================================"
    )
    print(
        "EXPORT SQLITE -> JSONL"
    )
    print(
        "========================================"
    )

    create_database()

    connection = sqlite3.connect(
        DATABASE_FILE
    )

    cursor = connection.cursor()

    # --------------------------------------------------------
    # Выбираем только полностью готовые документы,
    # у которых реально есть result_json.
    # --------------------------------------------------------

    cursor.execute(
        """
        SELECT
            doc_id,
            result_json

        FROM documents

        WHERE
            status = 'done'
            AND result_json IS NOT NULL

        ORDER BY created_at
        """
    )

    rows = cursor.fetchall()

    print(
        "Do eksportu:",
        len(rows)
    )

    exported = 0

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as output:

        for doc_id, result_json in rows:

            try:

                # Проверяем, что внутри действительно
                # правильный JSON.
                record = json.loads(
                    result_json
                )

            except json.JSONDecodeError:

                print(
                    "BŁĘDNY JSON:",
                    doc_id
                )

                continue

            output.write(
                json.dumps(
                    record,
                    ensure_ascii=False
                )
            )

            output.write(
                "\n"
            )

            exported += 1

    connection.close()

    print(
        "\nWyeksportowano:",
        exported
    )

    print(
        "Plik:",
        OUTPUT_FILE
    )


if __name__ == "__main__":
    main()
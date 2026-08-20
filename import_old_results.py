import json
import sqlite3
from datetime import datetime

from database import (
    DATABASE_FILE,
    create_database,
)


RESULTS_FILE = "results.jsonl"


def main():

    print(
        "========================================"
    )
    print(
        "IMPORT STARYCH WYNIKÓW DO SQLITE"
    )
    print(
        "========================================"
    )

    # --------------------------------------------------------
    # 1. Убеждаемся, что структура базы актуальная.
    # --------------------------------------------------------

    create_database()

    connection = sqlite3.connect(
        DATABASE_FILE
    )

    cursor = connection.cursor()

    imported = 0
    already_present = 0
    not_found = 0
    invalid = 0

    # --------------------------------------------------------
    # 2. Читаем JSONL построчно.
    #
    # В нашем старом файле:
    #
    # строка 1 = документ 1
    # строка 2 = документ 2
    # ...
    # --------------------------------------------------------

    with open(
        RESULTS_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        for line_number, line in enumerate(
            file,
            start=1
        ):

            line = line.strip()

            if not line:
                continue

            # ------------------------------------------------
            # 3. Превращаем JSON-текст
            # обратно в словарь Python.
            # ------------------------------------------------

            try:

                record = json.loads(
                    line
                )

            except json.JSONDecodeError as error:

                invalid += 1

                print(
                    f"Linia {line_number}: "
                    f"niepoprawny JSON:"
                )

                print(
                    error
                )

                continue

            # ------------------------------------------------
            # 4. Берём doc_id.
            # ------------------------------------------------

            doc_id = record.get(
                "doc_id"
            )

            if not doc_id:

                invalid += 1

                print(
                    f"Linia {line_number}: "
                    "brak doc_id."
                )

                continue

            # ------------------------------------------------
            # 5. Проверяем запись в SQLite.
            # ------------------------------------------------

            cursor.execute(
                """
                SELECT
                    status,
                    result_json

                FROM documents

                WHERE doc_id = ?
                """,
                (doc_id,)
            )

            row = cursor.fetchone()

            if row is None:

                not_found += 1

                print(
                    doc_id,
                    "NIE MA W BAZIE"
                )

                continue

            status, existing_result = row

            # ------------------------------------------------
            # 6. Если result_json уже заполнен,
            # ничего не перезаписываем.
            # ------------------------------------------------

            if existing_result:

                already_present += 1

                print(
                    doc_id,
                    "JUŻ MA RESULT_JSON"
                )

                continue

            # ------------------------------------------------
            # 7. Превращаем весь словарь снова
            # в JSON для хранения в SQLite.
            # ------------------------------------------------

            result_json = json.dumps(
                record,
                ensure_ascii=False
            )

            now = datetime.now().isoformat(
                timespec="seconds"
            )

            # ------------------------------------------------
            # 8. Записываем результат.
            #
            # Статус одновременно оставляем done.
            # ------------------------------------------------

            cursor.execute(
                """
                UPDATE documents

                SET
                    result_json = ?,
                    status = 'done',
                    last_error = NULL,
                    updated_at = ?

                WHERE doc_id = ?
                """,
                (
                    result_json,
                    now,
                    doc_id,
                )
            )

            imported += 1

            print(
                doc_id,
                "ZAIMPORTOWANO"
            )

    # --------------------------------------------------------
    # 9. Только теперь сохраняем все изменения.
    # --------------------------------------------------------

    connection.commit()

    # --------------------------------------------------------
    # 10. Проверка.
    # --------------------------------------------------------

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM documents
        WHERE status = 'done'
        """
    )

    done_count = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM documents
        WHERE result_json IS NOT NULL
        """
    )

    result_count = cursor.fetchone()[0]

    connection.close()

    print(
        "\n========================================"
    )
    print(
        "PODSUMOWANIE"
    )
    print(
        "========================================"
    )

    print(
        "Zaimportowano:",
        imported
    )

    print(
        "Już miało wynik:",
        already_present
    )

    print(
        "Nie znaleziono w bazie:",
        not_found
    )

    print(
        "Niepoprawne rekordy:",
        invalid
    )

    print(
        "Status DONE:",
        done_count
    )

    print(
        "Rekordy z result_json:",
        result_count
    )


if __name__ == "__main__":
    main()
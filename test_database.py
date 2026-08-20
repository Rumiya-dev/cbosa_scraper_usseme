from database import (
    create_database,
    add_document,
    count_documents,
    count_by_status,
    get_pending_documents,
    mark_done,
    show_documents,
)


def main():

    print(
        "========================================"
    )

    print(
        "TEST SQLITE"
    )

    print(
        "========================================"
    )

    # Создаём базу и таблицу.
    create_database()

    print(
        "Baza została utworzona."
    )

    # --------------------------------------------------------
    # Добавляем 3 тестовых документа.
    # --------------------------------------------------------

    test_documents = [

        (
            "TEST000001",
            "https://example.com/doc/TEST000001"
        ),

        (
            "TEST000002",
            "https://example.com/doc/TEST000002"
        ),

        (
            "TEST000003",
            "https://example.com/doc/TEST000003"
        ),
    ]

    print(
        "\nDodaję dokumenty..."
    )

    for doc_id, url in test_documents:

        inserted = add_document(
            doc_id,
            url
        )

        print(
            doc_id,
            "NOWY"
            if inserted
            else "JUŻ ISTNIEJE"
        )

    # --------------------------------------------------------
    # Считаем записи.
    # --------------------------------------------------------

    print(
        "\nWszystkich:",
        count_documents()
    )

    print(
        "Pending:",
        count_by_status(
            "pending"
        )
    )

    print(
        "Done:",
        count_by_status(
            "done"
        )
    )

    # --------------------------------------------------------
    # Показываем pending.
    # --------------------------------------------------------

    print(
        "\nDokumenty pending:"
    )

    pending = get_pending_documents(
        limit=10
    )

    for doc_id, url in pending:

        print(
            doc_id,
            url
        )

    # --------------------------------------------------------
    # Помечаем один документ выполненным.
    # --------------------------------------------------------

    print(
        "\nZmieniam TEST000001 "
        "na DONE..."
    )

    mark_done(
        "TEST000001"
    )

    # --------------------------------------------------------
    # Новая статистика.
    # --------------------------------------------------------

    print(
        "\nPo zmianie:"
    )

    print(
        "Pending:",
        count_by_status(
            "pending"
        )
    )

    print(
        "Done:",
        count_by_status(
            "done"
        )
    )

    # --------------------------------------------------------
    # Показываем таблицу.
    # --------------------------------------------------------

    print(
        "\nRekordy w bazie:"
    )

    rows = show_documents(
        limit=20
    )

    for row in rows:

        print(
            row
        )


if __name__ == "__main__":
    main()
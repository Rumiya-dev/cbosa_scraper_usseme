import json
import sqlite3
from datetime import datetime


DATABASE_FILE = "cbosa.db"


# ============================================================
# POŁĄCZENIE
# ============================================================

def get_connection():
    """
    Otwiera połączenie z SQLite.
    """

    connection = sqlite3.connect(
        DATABASE_FILE
    )

    return connection


# ============================================================
# TWORZENIE / MIGRACJA BAZY
# ============================================================

def create_database():
    """
    Tworzy tabelę documents.

    Jeżeli baza już istnieje, zachowuje dane.

    Dodajemy też kolumnę result_json,
    jeżeli jej jeszcze nie ma.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS documents (
            doc_id TEXT PRIMARY KEY,
            url TEXT NOT NULL,

            status TEXT NOT NULL
                DEFAULT 'pending',

            attempts INTEGER NOT NULL
                DEFAULT 0,

            last_error TEXT,

            result_json TEXT,

            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    # --------------------------------------------------------
    # Stara baza może jeszcze nie mieć result_json.
    #
    # Sprawdzamy więc listę kolumn.
    # --------------------------------------------------------

    cursor.execute(
        """
        PRAGMA table_info(documents)
        """
    )

    columns = {
        row[1]
        for row in cursor.fetchall()
    }

    if "result_json" not in columns:

        print(
            "Migracja: dodaję kolumnę result_json..."
        )

        cursor.execute(
            """
            ALTER TABLE documents
            ADD COLUMN result_json TEXT
            """
        )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_documents_status_created

        ON documents (
            status,
            created_at
        )
        """
    )
    connection.commit()
    connection.close()


# ============================================================
# DODAWANIE ID
# ============================================================

def add_document(
    doc_id,
    url
):
    """
    Dodaje jeden dokument.

    Jeśli doc_id już istnieje,
    nie tworzy duplikatu.
    """

    now = datetime.now().isoformat(
        timespec="seconds"
    )

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT OR IGNORE INTO documents (
            doc_id,
            url,
            status,
            attempts,
            created_at,
            updated_at
        )
        VALUES (?, ?, 'pending', 0, ?, ?)
        """,
        (
            doc_id,
            url,
            now,
            now,
        )
    )

    inserted = (
        cursor.rowcount == 1
    )

    connection.commit()
    connection.close()

    return inserted


def add_documents(urls):
    """
    Dodaje wiele dokumentów w jednej transakcji.

    To jest znacznie szybsze niż otwieranie
    SQLite osobno dla każdego dokumentu.
    """

    now = datetime.now().isoformat(
        timespec="seconds"
    )

    connection = get_connection()
    cursor = connection.cursor()

    new_count = 0
    existing_count = 0

    try:

        for url in urls:

            doc_id = (
                url.rstrip("/")
                .split("/")[-1]
            )

            cursor.execute(
                """
                INSERT OR IGNORE INTO documents (
                    doc_id,
                    url,
                    status,
                    attempts,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, 'pending', 0, ?, ?)
                """,
                (
                    doc_id,
                    url,
                    now,
                    now,
                )
            )

            if cursor.rowcount == 1:

                new_count += 1

            else:

                existing_count += 1

        # Один commit на всю страницу.
        connection.commit()

    except Exception:

        connection.rollback()
        raise

    finally:

        connection.close()

    return (
        new_count,
        existing_count
    )
# ============================================================
# STATYSTYKI
# ============================================================

def count_documents():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM documents
        """
    )

    value = cursor.fetchone()[0]

    connection.close()

    return value


def count_by_status(status):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM documents
        WHERE status = ?
        """,
        (status,)
    )

    value = cursor.fetchone()[0]

    connection.close()

    return value


# ============================================================
# KOLEJKA DO PRZETWARZANIA
# ============================================================

def get_documents_to_process(
    limit=10,
    max_attempts=3
):
    """
    Pobiera:

    1. dokumenty pending

    ALBO

    2. dokumenty failed,
       ale tylko jeśli attempts < max_attempts.

    Dzięki temu błędy mogą zostać
    automatycznie ponowione.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            doc_id,
            url,
            status,
            attempts

        FROM documents

        WHERE
            status = 'pending'

            OR

            (
                status = 'failed'
                AND attempts < ?
            )

        ORDER BY
            CASE
                WHEN status = 'pending'
                THEN 0
                ELSE 1
            END,
            created_at

        LIMIT ?
        """,
        (
            max_attempts,
            limit,
        )
    )

    rows = cursor.fetchall()

    connection.close()

    return rows


# Старую функцию оставляем,
# чтобы другие тестовые файлы не сломались.

def get_pending_documents(limit=10):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT doc_id, url

        FROM documents

        WHERE status = 'pending'

        ORDER BY created_at

        LIMIT ?
        """,
        (limit,)
    )

    rows = cursor.fetchall()

    connection.close()

    return rows


# ============================================================
# УСПЕШНЫЙ РЕЗУЛЬТАТ
# ============================================================

def save_document_result(
    doc_id,
    result
):
    """
    Atomowo zapisuje wynik + status done.

    result jest słownikiem Python.
    Zamieniamy go na JSON.
    """

    now = datetime.now().isoformat(
        timespec="seconds"
    )

    result_json = json.dumps(
        result,
        ensure_ascii=False
    )

    connection = get_connection()

    try:

        cursor = connection.cursor()

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

        connection.commit()

    except Exception:

        connection.rollback()
        raise

    finally:

        connection.close()


# ============================================================
# BŁĄD
# ============================================================

def mark_failed(
    doc_id,
    error_message
):
    """
    Dokument dostaje status failed.

    attempts zwiększamy o 1.
    """

    now = datetime.now().isoformat(
        timespec="seconds"
    )

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE documents

        SET
            status = 'failed',
            attempts = attempts + 1,
            last_error = ?,
            updated_at = ?

        WHERE doc_id = ?
        """,
        (
            str(error_message),
            now,
            doc_id,
        )
    )

    connection.commit()
    connection.close()


# ============================================================
# KOMPATYBILNOŚĆ ZE STARYMI TESTAMI
# ============================================================

def mark_done(doc_id):

    now = datetime.now().isoformat(
        timespec="seconds"
    )

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE documents

        SET
            status = 'done',
            updated_at = ?

        WHERE doc_id = ?
        """,
        (
            now,
            doc_id,
        )
    )

    connection.commit()
    connection.close()


def increase_attempts(doc_id):

    now = datetime.now().isoformat(
        timespec="seconds"
    )

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE documents

        SET
            attempts = attempts + 1,
            updated_at = ?

        WHERE doc_id = ?
        """,
        (
            now,
            doc_id,
        )
    )

    connection.commit()
    connection.close()


# ============================================================
# PODGLĄD
# ============================================================

def show_documents(limit=20):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            doc_id,
            status,
            attempts,
            url

        FROM documents

        ORDER BY created_at

        LIMIT ?
        """,
        (limit,)
    )

    rows = cursor.fetchall()

    connection.close()

    return rows

# ============================================================
# SEARCH JOBS - CHECKPOINT PAGINACJI
# ============================================================

def create_search_jobs_table():
    """
    Tworzy tabelę przechowującą postęp
    zbierania stron wyników CBOSA.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS search_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            date_from TEXT NOT NULL,
            date_to TEXT NOT NULL,

            next_page INTEGER NOT NULL
                DEFAULT 1,

            total_pages INTEGER,

            status TEXT NOT NULL
                DEFAULT 'running',

            last_error TEXT,

            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,

            UNIQUE(date_from, date_to)
        )
        """
    )

    connection.commit()
    connection.close()


def get_or_create_search_job(
    date_from,
    date_to,
    start_page=1
):
    """
    Pobiera istniejący checkpoint.

    Jeżeli jeszcze go nie ma,
    tworzy nowy.
    """

    now = datetime.now().isoformat(
        timespec="seconds"
    )

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT OR IGNORE INTO search_jobs (
            date_from,
            date_to,
            next_page,
            status,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, 'running', ?, ?)
        """,
        (
            date_from,
            date_to,
            start_page,
            now,
            now,
        )
    )

    connection.commit()

    cursor.execute(
        """
        SELECT
            id,
            date_from,
            date_to,
            next_page,
            total_pages,
            status

        FROM search_jobs

        WHERE
            date_from = ?
            AND date_to = ?
        """,
        (
            date_from,
            date_to,
        )
    )

    row = cursor.fetchone()

    connection.close()

    return row


def update_search_total_pages(
    job_id,
    total_pages
):
    """
    Zapisuje całkowitą liczbę stron.
    """

    now = datetime.now().isoformat(
        timespec="seconds"
    )

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE search_jobs

        SET
            total_pages = ?,
            updated_at = ?,
            last_error = NULL

        WHERE id = ?
        """,
        (
            total_pages,
            now,
            job_id,
        )
    )

    connection.commit()
    connection.close()


def update_search_next_page(
    job_id,
    next_page
):
    """
    Zapisuje numer następnej strony,
    którą należy pobrać.
    """

    now = datetime.now().isoformat(
        timespec="seconds"
    )

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE search_jobs

        SET
            next_page = ?,
            status = 'running',
            updated_at = ?,
            last_error = NULL

        WHERE id = ?
        """,
        (
            next_page,
            now,
            job_id,
        )
    )

    connection.commit()
    connection.close()


def mark_search_job_done(job_id):
    """
    Oznacza cały zakres wyszukiwania
    jako zakończony.
    """

    now = datetime.now().isoformat(
        timespec="seconds"
    )

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE search_jobs

        SET
            status = 'done',
            updated_at = ?,
            last_error = NULL

        WHERE id = ?
        """,
        (
            now,
            job_id,
        )
    )

    connection.commit()
    connection.close()


def mark_search_job_error(
    job_id,
    error_message
):
    """
    Zapisuje ostatni błąd kolektora.
    """

    now = datetime.now().isoformat(
        timespec="seconds"
    )

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE search_jobs

        SET
            last_error = ?,
            updated_at = ?

        WHERE id = ?
        """,
        (
            str(error_message),
            now,
            job_id,
        )
    )

    connection.commit()
    connection.close()


def show_search_jobs():
    """
    Pokazuje wszystkie checkpointy.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            id,
            date_from,
            date_to,
            next_page,
            total_pages,
            status

        FROM search_jobs

        ORDER BY id
        """
    )

    rows = cursor.fetchall()

    connection.close()

    return rows

# ============================================================
# KOLEJKA ZAKRESÓW DAT
# ============================================================

def create_search_job(
    date_from,
    date_to
):
    """
    Dodaje nowy zakres dat do search_jobs.

    Jeżeli identyczny zakres już istnieje,
    nie tworzy duplikatu.
    """

    now = datetime.now().isoformat(
        timespec="seconds"
    )

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT OR IGNORE INTO search_jobs (
            date_from,
            date_to,
            next_page,
            status,
            created_at,
            updated_at
        )
        VALUES (?, ?, 1, 'running', ?, ?)
        """,
        (
            date_from,
            date_to,
            now,
            now,
        )
    )

    inserted = (
        cursor.rowcount == 1
    )

    connection.commit()
    connection.close()

    return inserted


def get_next_search_job():
    """
    Zwraca pierwszy niezakończony zakres.

    Kolejność jest według daty od najstarszego.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            id,
            date_from,
            date_to,
            next_page,
            total_pages,
            status

        FROM search_jobs

        WHERE status != 'done'

        ORDER BY
            date_from,
            date_to

        LIMIT 1
        """
    )

    row = cursor.fetchone()

    connection.close()

    return row


def count_search_jobs_by_status(
    status
):
    """
    Liczy zakresy o danym statusie.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)

        FROM search_jobs

        WHERE status = ?
        """,
        (status,)
    )

    value = cursor.fetchone()[0]

    connection.close()

    return value
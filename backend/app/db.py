import os

import psycopg
from psycopg.rows import dict_row


def connect():
    return psycopg.connect(
        os.getenv("DATABASE_URL", "postgresql://factorypulse:factorypulse_dev@localhost:5432/factorypulse"),
        row_factory=dict_row,
        connect_timeout=5,
    )


def query(sql: str, params: tuple = ()) -> list[dict]:
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute(sql, params)
        return list(cursor.fetchall())

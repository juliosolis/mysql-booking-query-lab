"""Reproducible, fictional MySQL booking query benchmark."""

import json
import os
import random
import statistics
import time
from datetime import date, timedelta

import mysql.connector

DATABASE = "portfolio_booking_lab"
ROWS = 120_000
QUERY = """SELECT COUNT(*), COALESCE(SUM(amount_cents), 0)
FROM reservations
WHERE hotel_id = %s AND status = %s AND check_in >= %s AND check_in < %s"""
PARAMS = (17, "confirmed", "2025-05-01", "2025-08-01")


def connect():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3318")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        connection_timeout=10,
    )


def prepare(connection):
    cursor = connection.cursor()
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DATABASE}")
    cursor.execute(f"USE {DATABASE}")
    cursor.execute("""CREATE TABLE IF NOT EXISTS reservations (
        id BIGINT PRIMARY KEY,
        hotel_id INT NOT NULL,
        status VARCHAR(20) NOT NULL,
        check_in DATE NOT NULL,
        amount_cents INT NOT NULL
    ) ENGINE=InnoDB""")
    cursor.execute("SELECT COUNT(*) FROM reservations")
    count = cursor.fetchone()[0]
    if count == 0:
        rng = random.Random(20261012)
        start = date(2025, 1, 1)
        for offset in range(0, ROWS, 2000):
            values = [
                (index, rng.randint(1, 50), rng.choice(("confirmed", "confirmed", "cancelled", "pending")),
                 start + timedelta(days=rng.randrange(365)), rng.randint(8000, 60000))
                for index in range(offset + 1, min(offset + 2000, ROWS) + 1)
            ]
            cursor.executemany("INSERT INTO reservations VALUES (%s,%s,%s,%s,%s)", values)
        connection.commit()
    elif count != ROWS:
        raise RuntimeError(f"Expected {ROWS} rows in {DATABASE}.reservations, found {count}; use a clean local instance")
    cursor.execute("SHOW INDEX FROM reservations WHERE Key_name = 'idx_hotel_status_arrival'")
    if cursor.fetchall():
        cursor.execute("ALTER TABLE reservations DROP INDEX idx_hotel_status_arrival")
    cursor.execute("ANALYZE TABLE reservations")
    cursor.fetchall()
    cursor.close()


def measure(connection, runs=20):
    cursor = connection.cursor()
    cursor.execute("EXPLAIN FORMAT=JSON " + QUERY, PARAMS)
    plan = json.loads(cursor.fetchone()[0])
    cursor.execute(QUERY, PARAMS)
    expected = cursor.fetchone()
    samples = []
    for _ in range(runs):
        started = time.perf_counter_ns()
        cursor.execute(QUERY, PARAMS)
        result = cursor.fetchone()
        samples.append((time.perf_counter_ns() - started) / 1_000_000)
        assert result == expected
    cursor.close()
    return {"median_ms": round(statistics.median(samples), 3), "min_ms": round(min(samples), 3),
            "max_ms": round(max(samples), 3), "rows": expected[0], "amount_cents": int(expected[1]), "plan": plan}


def main():
    connection = connect()
    try:
        prepare(connection)
        before = measure(connection)
        cursor = connection.cursor()
        cursor.execute("ALTER TABLE reservations ADD INDEX idx_hotel_status_arrival (hotel_id, status, check_in)")
        cursor.execute("ANALYZE TABLE reservations")
        cursor.fetchall()
        cursor.close()
        after = measure(connection)
        assert (before["rows"], before["amount_cents"]) == (after["rows"], after["amount_cents"])
        output = {"mysql_version": connection.server_info, "synthetic_rows": ROWS,
                  "query": QUERY.strip(), "params": PARAMS, "before": before, "after": after,
                  "median_speedup": round(before["median_ms"] / after["median_ms"], 2)}
        os.makedirs("results", exist_ok=True)
        with open("results/benchmark.json", "w", encoding="utf-8") as handle:
            json.dump(output, handle, indent=2)
        print(json.dumps({key: output[key] for key in ("mysql_version", "synthetic_rows", "median_speedup")}, indent=2))
        print(f"Before: {before['median_ms']} ms; after: {after['median_ms']} ms; equal result: {after['rows']} bookings")
        print("Full plans and measurements: results/benchmark.json")
    finally:
        connection.close()


if __name__ == "__main__":
    main()

import os
import time

_driver = None
_down_until = 0.0
COOLDOWN = 30
last_error = None


def config():
    return {
        "uri": os.environ.get("NEO4J_URI", "").strip(),
        "user": os.environ.get("NEO4J_USER", "neo4j"),
        "password": os.environ.get("NEO4J_PASSWORD", ""),
        "database": os.environ.get("NEO4J_DATABASE", "neo4j"),
    }


def enabled():
    return bool(config()["uri"])


def get_driver():
    global _driver, last_error
    if not enabled():
        return None
    if _driver is None:
        try:
            from neo4j import GraphDatabase
        except ImportError:
            last_error = "Paket 'neo4j' belum terpasang (pip install -r requirements.txt)."
            return None
        c = config()
        _driver = GraphDatabase.driver(
            c["uri"], auth=(c["user"], c["password"]),
            connection_timeout=3,
            connection_acquisition_timeout=5,
            max_transaction_retry_time=2,
        )
    return _driver


def run(query, **params):
    global _down_until
    if time.time() < _down_until:
        raise RuntimeError(last_error or "Neo4j baru saja tidak bisa diakses.")
    driver = get_driver()
    if driver is None:
        raise RuntimeError(last_error or "Neo4j belum diatur (NEO4J_URI kosong).")
    try:
        records, _, _ = driver.execute_query(query, parameters_=params,
                                             database_=config()["database"])
    except Exception as e:
        if _is_connection_error(e):
            _down_until = time.time() + COOLDOWN
        raise
    return [r.data() for r in records]


def _is_connection_error(e):
    try:
        from neo4j.exceptions import ServiceUnavailable, AuthError, SessionExpired
    except ImportError:
        return False
    return isinstance(e, (ServiceUnavailable, AuthError, SessionExpired, OSError))


def safe_run(query, **params):
    global last_error
    try:
        result = run(query, **params)
        last_error = None
        return result
    except Exception as e:
        if not isinstance(e, RuntimeError):
            last_error = f"{type(e).__name__}: {e}"
        return None

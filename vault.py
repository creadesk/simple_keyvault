import os
import re
import sqlite3
import getpass
import threading
import time
import stat

from pathlib import Path
from contextlib import contextmanager

import uvicorn

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from cryptography.fernet import Fernet, InvalidToken


DATA = Path("/data")
DB = DATA / "vault.db"
SOCKET_DIR = Path("/run/keyvault")
SOCKET = SOCKET_DIR / "vault.sock"

VAULT_UID = 10001
VAULT_GID = 20000

CHECK_VALUE = b"PYTHON_KEYVAULT_MASTER_KEY_VALID"

cipher = None


# SQLite-Verbindungen
@contextmanager
def connect():
    db = sqlite3.connect(DB, timeout=10)
    db.execute("PRAGMA busy_timeout=10000")

    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# Datenbank initialisieren und Master-Key prüfen
def initialize_storage():
    with connect() as db:

        db.execute("""
            CREATE TABLE IF NOT EXISTS secrets (
                name TEXT PRIMARY KEY,
                value BLOB NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS vault_meta (
                name TEXT PRIMARY KEY,
                value BLOB NOT NULL
            )
        """)

        result = db.execute(
            "SELECT value FROM vault_meta WHERE name='key_check'"
        ).fetchone()

        if result is None:
            count = db.execute(
                "SELECT COUNT(*) FROM secrets"
            ).fetchone()[0]

            if count:
                raise RuntimeError(
                    "Datenbank ohne Master-Key-Prüfwert. "
                    "Sicherheitsprüfung abgebrochen."
                )

            verifier = cipher.encrypt(CHECK_VALUE)

            db.execute(
                "INSERT INTO vault_meta (name, value) VALUES (?, ?)",
                ("key_check", verifier)
            )

        else:
            try:
                decrypted = cipher.decrypt(result[0])

                if decrypted != CHECK_VALUE:
                    raise RuntimeError("Master-Key ungültig")

            except InvalidToken:
                raise RuntimeError(
                    "FALSCHER MASTER-KEY! Vault bleibt gesperrt."
                )

    os.chmod(DB, 0o600)


# Schlüsselname validieren
def validate_name(name):
    if not re.fullmatch(r"[a-zA-Z0-9_.-]{1,100}", name):
        raise HTTPException(400, "Ungültiger Schlüsselname")


app = FastAPI(
    title="Python Key Vault",
    docs_url=None,
    redoc_url=None
)


class SecretInput(BaseModel):
    value: str = Field(min_length=1, max_length=10000)


@app.get("/health")
def health():
    return {"status": "unlocked"}


@app.get("/keys/{name}")
def get_secret(name: str):
    validate_name(name)

    with connect() as db:
        result = db.execute(
            "SELECT value FROM secrets WHERE name=?",
            (name,)
        ).fetchone()

    if result is None:
        raise HTTPException(404, "Schlüssel nicht gefunden")

    try:
        value = cipher.decrypt(result[0]).decode("utf-8")
    except (InvalidToken, UnicodeDecodeError):
        raise HTTPException(500, "Entschlüsselung fehlgeschlagen")

    return {"name": name, "value": value}


@app.put("/keys/{name}")
def set_secret(name: str, body: SecretInput):
    validate_name(name)

    encrypted = cipher.encrypt(body.value.encode("utf-8"))

    with connect() as db:
        db.execute("""
            INSERT INTO secrets (name, value)
            VALUES (?, ?)
            ON CONFLICT(name) DO UPDATE SET
                value=excluded.value,
                updated_at=CURRENT_TIMESTAMP
        """, (name, encrypted))

    return {"status": "ok", "name": name}


@app.delete("/keys/{name}")
def delete_secret(name: str):
    validate_name(name)

    with connect() as db:
        cursor = db.execute(
            "DELETE FROM secrets WHERE name=?",
            (name,)
        )

        if cursor.rowcount == 0:
            raise HTTPException(404, "Nicht gefunden")

    return {"status": "deleted"}


def main():
    global cipher

    print("\n================================")
    print("       PYTHON KEY VAULT")
    print("================================")

    key = getpass.getpass(
        "Master-Key eingeben: ",
        stream=None
    )

    try:
        cipher = Fernet(key.encode("ascii"))
    except Exception:
        raise SystemExit("Ungültiges Master-Key-Format")

    DATA.mkdir(parents=True, exist_ok=True)
    SOCKET_DIR.mkdir(parents=True, exist_ok=True)

    if os.geteuid() != 0:
        raise SystemExit("Vault muss initial als Container-Root starten")

    os.chown(DATA, VAULT_UID, VAULT_GID)
    os.chmod(DATA, 0o700)

    os.chown(SOCKET_DIR, VAULT_UID, VAULT_GID)
    os.chmod(SOCKET_DIR, 0o2770)

    initialize_storage()

    os.chown(DB, VAULT_UID, VAULT_GID)

    if SOCKET.exists():
        if not stat.S_ISSOCK(SOCKET.lstat().st_mode):
            raise SystemExit("Socket-Pfad ist keine Socket-Datei")
        SOCKET.unlink()

    # Ab hier läuft der eigentliche Dienst ohne Root-Rechte.
    os.setgroups([VAULT_GID])
    os.setgid(VAULT_GID)
    os.setuid(VAULT_UID)

    print("\nMaster-Key akzeptiert.")
    print("Starte Vault...")

    server = uvicorn.Server(
        uvicorn.Config(
            app,
            uds=str(SOCKET),
            workers=1,
            access_log=False,
            log_level="warning"
        )
    )

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    for _ in range(100):
        if SOCKET.exists() and stat.S_ISSOCK(SOCKET.lstat().st_mode):
            break
        if not thread.is_alive():
            raise SystemExit("Vault konnte nicht gestartet werden")
        time.sleep(0.1)
    else:
        server.should_exit = True
        raise SystemExit("Vault Socket wurde nicht erstellt")

    os.chmod(SOCKET, 0o660)

    print("Vault erfolgreich entsperrt.")
    print("Socket:", SOCKET)

    # Integrierter Funktionstest
    from test_client import main as run_test

    run_test()

    print("\nVault ist betriebsbereit.")
    print("Container mit STRG+P, danach STRG+Q verlassen (Container läuft weiter).\n")
    print("Container mit STRG+C beenden.\n")

    try:
        thread.join()
    except KeyboardInterrupt:
        print("\nVault wird gesperrt...")
        server.should_exit = True
        thread.join()
        print("Vault beendet.")


if __name__ == "__main__":
    main()
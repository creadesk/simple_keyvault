from vault_client import Vault


def main():
    print("\n=== KEY VAULT TEST ===")

    with Vault() as vault:

        print("[1] Testschlüssel speichern")

        vault.set(
            "test.database.password",
            "MeinGeheimesPasswort123"
        )

        print("[2] Testschlüssel abrufen")

        value = vault.get("test.database.password")

        assert value == "MeinGeheimesPasswort123"

        print("[OK] Schlüssel erfolgreich abgerufen")

        print("[3] Testschlüssel löschen")

        vault.delete("test.database.password")

        print("[OK] Schlüssel erfolgreich gelöscht")

    print("=== TEST ERFOLGREICH ===\n")
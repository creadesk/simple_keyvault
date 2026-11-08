import httpx


class Vault:

    def __init__(self, socket_path="/run/keyvault/vault.sock"):
        transport = httpx.HTTPTransport(uds=socket_path)

        self.client = httpx.Client(
            transport=transport,
            base_url="http://keyvault",
            timeout=5
        )

    def get(self, name):
        response = self.client.get(f"/keys/{name}")
        response.raise_for_status()
        return response.json()["value"]

    def set(self, name, value):
        response = self.client.put(
            f"/keys/{name}",
            json={"value": value}
        )
        response.raise_for_status()

    def delete(self, name):
        response = self.client.delete(f"/keys/{name}")
        response.raise_for_status()

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
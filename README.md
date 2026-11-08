> Ein einfacher python basierter Schlüsselspeicher.

> Zweck: Potenzielle Integration in andere Python-Projekte.
> Hier als eigenständiger Prototyp in Form eines Docker Containers.

> Das Design ist absichtlich so gewählt, dass bei jedem Start der Applikation der Master-Key manuell eingegeben werden muss.

> Der Master-Key wird an keiner Stelle persistiert.

### Projekt klonen
```bash
sudo apt install curl jq git
cd ~
git clone https://github.com/creadesk/simple_keyvault.git
Alternativ:
git clone https://codeberg.org/creadesk/simple_keyvault.git
```

### Image erstellen
```bash
sudo apt install -y docker.io
sudo apt install -y docker-buildx
sudo usermod -aG docker $USER
sudo reboot
cd simple_keyvault
docker build . -t simple_keyvault:latest
```

### Master-Key erzeugen
> Muss aus 32 kryptografisch zufälligen Bytes und URL-safer Codierung bestehen.

#### Alternative 1: mit Python
```bash
python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

#### Alternative 2: mit OpenSSL
```bash
openssl rand -base64 32 | tr '+/' '-_' | tr -d '\\n'
```

> Den so erzeugten Schlüssel sicher verwahren.

### Datenverzeichnis anlegen
```bash
mkdir data/
```

### Container starten:
```bash
docker run -it \
  --name simple_keyvault \
  --network none \
  -v $(pwd)/data:/data \
  simple_keyvault:latest
```

### Master Key eingeben
> Beim allerersten Start wird mit dem eingegebenen Master-Key der Prüfwert erzeugt und gespeichert.

> Container mit STRG+P, danach STRG+Q verlassen (Container läuft weiter).


### Container Logs ansehen
```bash
docker logs -f simple_keyvault
```

### Container stoppen
```bash
docker stop simple_keyvault
```

### Container wieder starten:
```bash
docker start -ai simple_keyvault
```

> Master-Key muss erneut manuell eingegeben werden

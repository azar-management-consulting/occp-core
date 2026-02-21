# QuickStart

Ez a dokumentum részletesen bemutatja, hogyan telepítheted az OCCP-t helyi fejlesztői környezetbe.

## Előfeltételek
- Docker és Docker Compose telepítve.
- Python 3.10+ és `pip`.

## Telepítés Dockerrel
1. Klónozd a repót és lépj be a mappába:

   ```bash
   git clone <repo-url> occp-core
   cd occp-core
   ```
2. Másold az `.env.example`-t `.env`-re és állítsd be a változókat.
3. Futtasd a következőt:

   ```bash
   docker compose up -d
   ```
4. Nyisd meg a `http://localhost:3000` címet a böngésződben.

## Telepítés CLI-vel
1. Telepítsd a CLI-t:

   ```bash
   pip install occp-cli
   ```
2. Indítsd el a rendszert:

   ```bash
   occp start
   ```

## Első workflow futtatása
Használd a webes felületet vagy a CLI-t egy JSON/YAML workflow futtatásához. Bővebb példa a `docs` mappában lesz.

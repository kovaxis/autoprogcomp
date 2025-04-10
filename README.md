# autoprogcomp

Actualizar un Google Sheets con información de la API de Codeforces.

Creado para el curso IIC2552 Taller de Programación Avanzada.

## Setup

1. Clonar repo.

2. Seguir [el quickstart de Google Sheets API para Python](https://developers.google.com/workspace/sheets/api/quickstart/python) para conseguir un archivo `credentials.json` con el que autorizar el script a modificar la spreadsheet. Colocar `credentials.json` en la carpeta `config`.

    NOTA: El archivo `credentials.json` abrirá una ventana de tu browser para darle permiso a `autoprogcomp` para acceder a tu cuenta.
    Tras darle permiso, se creará un archivo `token.json` en la carpeta `config`.
    Para correr `autoprogcomp` en un ambiente no-interactivo (ie. un servidor), hay que copiar el archivo `token.json` y no `credentials.json`.

3. Obtener una [API key para Codeforces](https://codeforces.com/settings/api).

4. Copiar `.env.example` -> `.env` (en la carpeta `config`) y rellenar `SPREADSHEET_ID`, `CODEFORCES_APIKEY` y `CODEFORCES_SECRET`.

5. Dependiendo si quieres usar Docker o no:

- Sin Docker (correr 1 vez):
    1. Instalar [`uv`](https://docs.astral.sh/uv/getting-started/installation/), y opcionalmente [`just`](https://github.com/casey/just?tab=readme-ov-file#installation).
    2. Correr el scraper con `just run` o `uv run python3 -m app.main`. Si no quieres instalar `uv`, puedes probar suerte instalando las librerías a mano y corriendo `python3 -m app.main`.

- Con Docker (correr regularmente):
    1. Correr `docker compose up --build --detach`. Se correrá regularmente el scraper, con un horario definido por la variable `SCHEDULE` del `.env`.

## Uso

Por defecto, al correr `autoprogcomp` este descarga la hoja `Codeforces` del spreadsheet configurado.
Esta hoja debiera en la columna `A2:A9999` contener handles de Codeforces de alumnos, y en la fila `B1:ZZZZ1` una serie de "comandos".

Los comandos pueden ser:

- `timeframe:<startDate>:<endDate>`: Este comando debe aparecer exactamente 1 vez. Indicar el rango de fechas en que considerar submissions.
- `contest`: Contar problemas resueltos por cada usuario en un contest particular, asignando una cierta cantidad de puntos a cada problema. Se pueden utilizar 4 sintaxis:
    - `contest:<contestId>`: Revisar el contest con ID `contestId` (numérico), y cada problema vale 1 punto. Equivalente a `contest:<contestId>:.*=1`.
    - `contest:<contestId>:a=1,b=2,c=3`: Revisar el contest con ID `contestId` (numérico), y asignar distinto puntaje a cada letra de problema. Se acepta regex para las letras de los problemas.
    - `contest:<groupCode>:<startDate>:a=1,b=2,c=3`: Revisar el primer contest del grupo `groupCode` (alfanumérico), que comience entre `startDate` y `startDate + 24h`.
    - `contest:<groupCode>:<rangeStart>:<rangeEnd>:a=1,b=2,c=3`: Revisar el primer contest del grupo `groupCode` (alfanumérico), que comience entre `rangeStart` y `rangeEnd`.
- `lang:<language>`: Contar cuántos problemas se han resuelto usando el lenguaje dado. Se considera que un problema se resolvió con `language` si `language` es un substring del lenguaje utilizado en la última submission OK del problema (case-insensitive).
- `coupons:<availableCoupons>`: Cuántos cupones tienen disponibles los alumnos. Los cupones permiten que las resoluciones de problemas fuera de tiempo cuenten para efectos del comando `contest`. Puede aparecer a lo más 1 vez.
- `rounds:<regex>`: Contar cuántos problemas se resolvieron en rondas oficiales (rated rounds) tales que el nombre de la ronda matchee con el patrón `regex`.

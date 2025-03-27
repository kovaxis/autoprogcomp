# autoprogcomp

Actualizar un Google Sheets con información de la API de Codeforces.

Creado para el curso IIC2552 Taller de Programación Avanzada.

## Uso

1. Clonar repo.
2. Seguir [el quickstart de Google Sheets API para Python](https://developers.google.com/workspace/sheets/api/quickstart/python) para conseguir un archivo `credentials.json` con el que autorizar el script a modificar la spreadsheet. Colocar `credentials.json` en la raíz del repositorio.
3. Obtener una [API key para Codeforces](https://codeforces.com/settings/api).
4. Copiar `.env.example` -> `.env` y rellenar `SPREADSHEET_ID`, `CODEFORCES_APIKEY` y `CODEFORCES_SECRET`.
5. Instalar [`uv`](https://docs.astral.sh/uv/getting-started/installation/), y opcionalmente [`just`](https://github.com/casey/just?tab=readme-ov-file#installation).
6. Correr el scraper con `just run` o `uv run python3 -m app.main`. Si no quieres instalar `uv`, puedes probar suerte instalando las librerías a mano y corriendo `python3 -m app.main`.

## Comandos

Por defecto, al correr `autoprogcomp` este descarga la hoja `Codeforces` del spreadsheet configurado.
Esta hoja debiera contener en la columna `A2:A` handles de Codeforces de alumnos, y en la fila `B1:1` una serie de "comandos".

Los comandos pueden ser:

- `timeframe:<startDate>:<endDate>`: Este comando debe aparecer exactamente 1 vez. Indicar el rango de fechas en que considerar submissions.
- `contest:<contestId>`/`contest:<contestId>:a=1,b=2,c=3`: Contar problemas resueltos por el usuario en el contest `contestId` (numérico). Opcionalmente se puede entregar un mapeo de problemas a puntajes.
- `lang:<language>`: Contar cuántos problemas se han resuelto usando el lenguaje dado. Se considera que un problema se resolvió con `language` si `language` es un substring del lenguaje utilizado en la última submission OK del problema (case-insensitive).
- `coupons:<availableCoupons>`: Cuántos cupones tienen disponibles los alumnos. Los cupones permiten que las resoluciones de problemas fuera de tiempo cuenten para efectos del comando `contest`.
- `rounds:<regex>`: Contar cuántos problemas se resolvieron en rondas oficiales (rated rounds) tales que el nombre de la ronda matchee con el patrón `regex`.

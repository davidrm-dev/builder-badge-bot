# Builder Badge Bot

Bot de Telegram que acompaña a un builder a completar las **21 badges de AWS Builder Center**
(las del reto que da $10 / $20 en créditos y el voucher de certificación).

Le mandas tu usuario de Builder Center, el bot lee tus badges desde la API pública, y todos los
días a la hora que elijas te manda la misión del día: rutina diaria, foco en las badges que te
faltan, estado de tus rachas y un mensaje motivador. Cuando detecta una badge nueva, te felicita.

## Qué se puede detectar automáticamente y qué no

| Dato | ¿Automático? | Cómo |
| --- | --- | --- |
| Badges ya ganadas | Sí | `GET https://api.builder.aws.com/rms/badges?bpId=...` (público, sin login) |
| `builderProfileId` a partir del alias | Sí | `POST https://api.builder.aws.com/ums/getProfileByAlias` |
| Progreso interno de una racha (día 4 de 7, etc.) | No | AWS no lo expone públicamente |

Por eso el progreso de rachas se lleva con los botones de "hecho" del mensaje diario: el bot
guarda tus check-ins y calcula la racha, y la badge real se confirma contra la API cuando AWS la
otorga.

## Comandos

- `/perfil davidrm` – conecta tu perfil (también acepta la URL completa)
- `/badges` – tablero con las 21 badges (✅/⬜) y progreso hacia 7/14/21
- `/hoy` – misión del día con botones de check-in
- `/sync` – revisa badges nuevas
- `/racha` – estado de rachas
- `/hora 08:00`, `/zona America/Bogota` – ajustan el recordatorio diario
- `/pausar`, `/activar`, `/borrar`

## Correr local

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # pon tu TELEGRAM_BOT_TOKEN de @BotFather
set -a && source .env && set +a
python -m bot.main
```

## Docker

```bash
docker build -t builder-badge-bot .
docker run -d --restart unless-stopped \
  -e TELEGRAM_BOT_TOKEN=xxx -v $PWD/data:/app/data builder-badge-bot
```

La base de datos SQLite vive en `data/bot.sqlite3` (configurable con `BOT_DB_PATH`).

## Tests

```bash
python -m pytest
```

## Licencia

MIT — ver [LICENSE](LICENSE).

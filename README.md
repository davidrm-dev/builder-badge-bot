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

## Desplegar en AWS (serverless, ~$0)

El mismo código corre en Lambda: si existe la variable `BOT_TABLE`, el bot usa DynamoDB en vez
de SQLite y los recordatorios los dispara EventBridge Scheduler en vez del job queue local.

```
Telegram ──webhook──▶ Lambda Function URL (bot.lambda_webhook)
                          │
EventBridge Scheduler ─▶ Lambda (bot.lambda_scheduler) ──▶ DynamoDB  ──▶ api.builder.aws.com
                          (cada 15 min, filtra por hora local de cada usuario)
```

| Recurso | Para qué | Costo típico |
| --- | --- | --- |
| Lambda (x2, arm64) | webhook + recordatorios | free tier: 1M req y 400k GB-s/mes |
| DynamoDB on-demand | usuarios, badges, check-ins (TTL 400 días) | free tier: 25 GB |
| EventBridge Scheduler | ~2.900 invocaciones/mes | free tier: 14M invocaciones |
| SSM Parameter Store | token de BotFather (SecureString) | Standard: gratis |

Los precios dependen de región, fecha y uso; verifica en la calculadora de AWS.

```bash
# 1. token en SSM (no viaja en el template ni queda en git)
aws ssm put-parameter --name /builder-badge-bot/telegram-token \
  --type SecureString --value "$TELEGRAM_BOT_TOKEN" --overwrite

# 2. secreto del webhook: Telegram lo manda en cada request y la Lambda lo valida
WEBHOOK_SECRET=$(openssl rand -hex 32)

# 3. desplegar
sam build
sam deploy --stack-name builder-badge-bot --resolve-s3 --capabilities CAPABILITY_IAM \
  --parameter-overrides WebhookSecret=$WEBHOOK_SECRET

# 4. registrar el webhook
URL=$(aws cloudformation describe-stacks --stack-name builder-badge-bot \
  --query "Stacks[0].Outputs[?OutputKey=='WebhookUrl'].OutputValue" --output text)
curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
  -d "url=$URL" -d "secret_token=$WEBHOOK_SECRET" -d "drop_pending_updates=true"
```

Para borrar todo: `sam delete --stack-name builder-badge-bot`.

### Alternativa: Lightsail / EC2

Si prefieres no portar nada, corre el `Dockerfile` tal cual en una instancia Lightsail
(bundle solo IPv6, ~$3.50/mes) con `--restart unless-stopped` y un volumen para `data/`.

## Tests

```bash
python -m pytest
```

## Licencia

MIT — ver [LICENSE](LICENSE).

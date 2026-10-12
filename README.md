# Builder Badge Bot

Coach por **Telegram o correo** que acompaña a un builder a completar las **21 badges de AWS Builder Center**
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
- `/idioma` – cambia entre español e inglés (también `/language en`)
- `/pausar`, `/activar`, `/borrar`

Cada comando tiene su alias en inglés (`/today`, `/streak`, `/time`, `/timezone`, `/pause`…) y
todos los textos viven en `bot/i18n.py`; agregar un idioma es añadir una clave a `STRINGS`.
Los mensajes traen botones que abren directo la sección de Builder Center que toca (leer,
escribir, wishlist, recompensas, tu perfil).

## Canal de correo

Para quien no usa Telegram: se inscribe en una página web con su correo, su alias y la hora, confirma
desde el correo y recibe cada día la misión (≤5 líneas) con botones de check-in.

- Los correos no reciben comandos, así que cada acción es un enlace firmado con HMAC
  (`EMAIL_LINK_SECRET`): confirmar, marcar un check-in, ver progreso y ajustes, darse de baja.
- Abrir un enlace de check-in no marca nada por sí solo: la página hace un POST con JS, porque los
  filtros de Outlook/Gmail abren los enlaces para escanearlos.
- Cada correo diario lleva `List-Unsubscribe` de un clic (lo exigen Gmail y Yahoo).
- Los usuarios de correo comparten tablas y lógica con los de Telegram (`bot/core.py`); WhatsApp
  entraría igual, como otro canal.

| Ruta | Para qué |
| --- | --- |
| `/` | inscripción |
| `/confirm` | confirma el correo y activa los envíos |
| `/c` | check-in de una tarea |
| `/me` | progreso, rachas, tablero y ajustes (hora, zona, idioma, pausa, borrar) |
| `/u` | baja |

### Configurar el dominio (una vez)

1. Despliega (abajo). El stack crea la identidad de SES para `EmailDomain` y deja en el output
   `DkimRecords` 3 registros CNAME: créalos en el DNS de tu dominio (donde lo compraste o en
   Route 53). SES lo verifica solo en unos minutos.
2. Recomendado: un TXT de DMARC, `_dmarc.davidrmdev.com` → `v=DMARC1; p=none;`.
3. SES arranca en *sandbox*: solo envía a direcciones verificadas (sirve para probar con la tuya).
   Para abrirlo a todos, pide acceso de producción en la consola de SES → *Account dashboard*.
4. Comparte el `SignupUrl` del output. Si quieres algo como `coach.davidrmdev.com`, ponlo delante
   con CloudFront y pásalo en `PublicBaseUrl`.

Si el dominio ya está verificado en SES en esa región, bórralo de la consola antes de desplegar
(CloudFormation no puede adoptar una identidad existente).

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
                          (cada 15 min, filtra por hora local) ──▶ Telegram / Amazon SES
Navegador ──────────────▶ Lambda Function URL (bot.web): inscripción, check-ins, ajustes
```

| Recurso | Para qué | Costo típico |
| --- | --- | --- |
| Lambda (x2, arm64) | webhook + recordatorios | free tier: 1M req y 400k GB-s/mes |
| DynamoDB on-demand | usuarios, badges, check-ins (TTL 400 días) | free tier: 25 GB |
| EventBridge Scheduler | ~2.900 invocaciones/mes | free tier: 14M invocaciones |
| SSM Parameter Store | token de BotFather (SecureString) | Standard: gratis |
| Amazon SES | correo diario y confirmaciones | ~$0,10 por 1.000 correos |
| Lambda web (Function URL) | páginas de inscripción, check-in y ajustes | free tier |

Los precios dependen de región, fecha y uso; verifica en la calculadora de AWS.

```bash
# 1. token en SSM (no viaja en el template ni queda en git)
aws ssm put-parameter --name /builder-badge-bot/telegram-token \
  --type SecureString --value "$TELEGRAM_BOT_TOKEN" --overwrite

# 2. secreto del webhook: Telegram lo manda en cada request y la Lambda lo valida
WEBHOOK_SECRET=$(openssl rand -hex 32)

# 3. desplegar (EMAIL_LINK_SECRET firma los enlaces de los correos: guárdalo, si cambia
#    los enlaces de baja de correos viejos dejan de funcionar)
EMAIL_LINK_SECRET=$(openssl rand -hex 32)
sam build
sam deploy --stack-name builder-badge-bot --resolve-s3 --capabilities CAPABILITY_IAM \
  --parameter-overrides WebhookSecret=$WEBHOOK_SECRET EmailLinkSecret=$EMAIL_LINK_SECRET \
    EmailDomain=davidrmdev.com "EmailFrom=Builder Badge Coach <coach@davidrmdev.com>"

# 4. registrar el webhook
URL=$(aws cloudformation describe-stacks --stack-name builder-badge-bot \
  --query "Stacks[0].Outputs[?OutputKey=='WebhookUrl'].OutputValue" --output text)
curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
  -d "url=$URL" -d "secret_token=$WEBHOOK_SECRET" -d "drop_pending_updates=true"
```

Para borrar todo: `sam delete --stack-name builder-badge-bot`.

**Alarmas (opcional):** agrega `AlertEmail=tu@correo.com` a `--parameter-overrides` y el stack crea
un tópico SNS y dos alarmas de CloudWatch que avisan si alguna Lambda falla en la última hora.
AWS te manda un correo para confirmar la suscripción. Sin ese parámetro no se crea nada.
El scheduler ya reintenta los cortes de red con Telegram (3 intentos con backoff), así que una
alarma significa que los reintentos se agotaron o que falló algo más.

Si despliegas con un usuario dedicado en vez de tu cuenta admin, en
[`docs/deploy-policy.json`](docs/deploy-policy.json) está la política mínima: solo permite tocar
recursos `builder-badge-bot*` y el bucket de artefactos de SAM.

### Alternativa: Lightsail / EC2

Si prefieres no portar nada, corre el `Dockerfile` tal cual en una instancia Lightsail
(bundle solo IPv6, ~$3.50/mes) con `--restart unless-stopped` y un volumen para `data/`.

## Tests

```bash
python -m pytest
```

## Licencia

MIT — ver [LICENSE](LICENSE).

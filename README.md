# portainer-telegram

Telegram-бот — минималистичный UI для управления Docker-контейнерами через Portainer API.
Разворачивается как stack прямо в Portainer, без монтирования docker.sock.

## Возможности

- `/ps` — список контейнеров со статусами (🟢 running, 🔴 exited, …)
- Inline-меню контейнера: Start / Stop / Restart, логи, статистика (CPU, RAM, NET, DISK)
- `/logs <имя> [n]` — последние n строк логов (по умолчанию 50)
- `/up <имя>`, `/down <имя>`, `/restart <имя>` — управление из командной строки
- Поддержка нескольких endpoints (окружений) Portainer — выбор кнопкой
- Whitelist чатов (`ALLOWED_CHAT_IDS`)

## Подготовка

1. **Бот**: создайте бота у [@BotFather](https://t.me/BotFather) и скопируйте токен.
2. **API-ключ Portainer**: My Account → API Tokens → Add token (роль: стандартный
   доступ к нужным endpoint'ам). Ключ показывается один раз — сохраните его.
3. **Ваш chat id**: напишите боту [@userinfobot](https://t.me/userinfobot) или
   посмотрите в BotFather → /mybots → API Token.

## Развёртывание в Portainer

1. Portainer → **Stacks → Add stack** → Web editor, вставьте
   (образ публикуется в GHCR из `main`):

   ```yaml
   services:
     portainer-telegram:
       image: ghcr.io/sozinovd/portainer-telegram:latest
       restart: unless-stopped
       environment:
         TELEGRAM_BOT_TOKEN: <токен>
         PORTAINER_URL: http://host.docker.internal:9000
         PORTAINER_API_KEY: <api-ключ>
         ALLOWED_CHAT_IDS: <ваш_chat_id>
       extra_hosts:
         - "host.docker.internal:host-gateway"
   ```

2. **Deploy the stack** и напишите боту `/ps`.

> `PORTAINER_URL`:
> - `http://host.docker.internal:9000` — порт Portainer опубликован на хосте (по умолчанию);
> - `http://portainer:9000` — если поместить контейнер в ту же docker-сеть, что и сервер Portainer.

### Сборка из исходников (форкам)

```bash
git clone <this-repo> && cd portainer-telegram
docker build -t portainer-telegram:latest .
```

и используйте `image: portainer-telegram:latest` в stack.

## CI

GitHub Actions (`.github/workflows/docker.yml`) на каждый push в `main` и теги `v*`:
собирает multi-arch образ (`linux/amd64`, `linux/arm64`) и публикует в
`ghcr.io/sozinovd/portainer-telegram`. Теги образа: `latest` (main), `X.Y.Z` /
`X.Y` (git-теги), `sha-<commit>`.

## Локальный запуск (для разработки)

```bash
cp .env.example .env   # заполните значения
docker compose up -d --build
```

или без Docker:

```bash
pip install -r requirements.txt
set -a; source .env; set +a
python -m bot.main
```

## Переменные окружения

| Переменная | Обязательная | Описание |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | да | Токен от @BotFather |
| `PORTAINER_API_KEY` | да | API-ключ Portainer |
| `PORTAINER_URL` | да | URL Portainer Server |
| `ALLOWED_CHAT_IDS` | нет | Chat id через запятую; пусто = доступ всем (небезопасно) |
| `PORTAINER_ENDPOINT_ID` | нет | Фиксировать endpoint; пусто = авто/выбор кнопкой |

## Как это работает

```
Telegram ⇄ aiogram (long polling)
              │
              ▼
       Portainer REST API (/api/endpoints/{id}/docker/...)
              │  X-API-Key
              ▼
         Docker Engine
```

Бот не требует доступа к `docker.sock` — все операции идут через HTTP API Portainer,
поэтому ему не нужны привилегированные режимы или монтирование сокета.

## License

MIT

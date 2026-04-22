# Telegram Notify Bot Rewire Runbook

## Why this broke

The legacy brain container started the OCCP API via `docker run -e OCCP_VOICE_TELEGRAM_BOT_TOKEN=...`
(inline `-e` flag). When we migrated to `docker compose up -d api` with the new image, that inline
env var was no longer injected — compose only loaded the explicit `environment:` array in
`docker-compose.yml`, which did not include the Telegram vars.

Fix: `docker-compose.yml` now declares `env_file: [.env]` on the `api:` service. Docker Compose
loads every `KEY=VALUE` line from `/opt/occp/.env` into the container at start. The explicit
`environment:` entries still override `.env` values (compose spec precedence).

## Verify on brain

```bash
# 1. Confirm .env exists on the brain
ls -la /opt/occp/.env

# 2. Recreate the container so env_file is picked up
cd /opt/occp && docker compose up -d --force-recreate api

# 3. Assert the token is now in the container environment
docker exec occp-core-api-1 env | grep TELEGRAM
# Expect: OCCP_VOICE_TELEGRAM_BOT_TOKEN=<token>
#         OCCP_VOICE_TELEGRAM_OWNER_CHAT_ID=<chat_id>
```

## Test notify end-to-end

```bash
# Replace $BOT_TOKEN and $CHAT_ID with the values from /opt/occp/.env
curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
  -d "chat_id=${CHAT_ID}" \
  -d "text=OCCP notify rewire OK $(date -u +%FT%TZ)"
# Expect: {"ok":true,"result":{...}}
```

## Recover the token if lost

1. Open Telegram, DM `@BotFather`.
2. Send `/mybots`, select `OccpBrainBot`.
3. Tap `API Token` → copy the `123456:ABC-...` string.
4. Paste into `/opt/occp/.env` as `OCCP_VOICE_TELEGRAM_BOT_TOKEN=...` (no quotes).
5. Owner chat ID: send any message to the bot, then
   `curl https://api.telegram.org/bot${BOT_TOKEN}/getUpdates` → `result[0].message.chat.id`.
6. `docker compose up -d --force-recreate api` to reload.

If the token was leaked (committed to git, pasted in Slack, etc.): revoke it via BotFather
`/revoke` before reusing the bot.

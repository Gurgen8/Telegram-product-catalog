#!/usr/bin/env bash
# Starts the HTTPS tunnel, writes its address to .env, starts the stack and registers the webhook.
set -euo pipefail
cd "$(dirname "$0")"

TUNNEL_PID_FILE=.tunnel.pid
TUNNEL_LOG=.tunnel.log
METRICS=127.0.0.1:20241

[ -f .env ] || { echo "Нет файла .env. Скопируйте .env.example в .env и заполните его."; exit 1; }
command -v cloudflared >/dev/null || { echo "Не найден cloudflared. Установите: brew install cloudflared"; exit 1; }
docker info >/dev/null 2>&1 || { echo "Docker не запущен. Откройте Docker Desktop и повторите."; exit 1; }

HTTP_PORT=$(grep -E '^HTTP_PORT=' .env | cut -d= -f2- || true)
HTTP_PORT=${HTTP_PORT:-8080}

# Stop a tunnel left over from a previous run.
if [ -f "$TUNNEL_PID_FILE" ] && kill -0 "$(cat "$TUNNEL_PID_FILE")" 2>/dev/null; then
  kill "$(cat "$TUNNEL_PID_FILE")" || true
  sleep 1
fi

echo "1/4 Запускаю туннель..."
nohup cloudflared tunnel --no-autoupdate --metrics "$METRICS" --url "http://localhost:$HTTP_PORT" \
  >"$TUNNEL_LOG" 2>&1 &
echo $! >"$TUNNEL_PID_FILE"

PUBLIC_URL=""
for _ in $(seq 1 60); do
  if grep -q "Registered tunnel connection" "$TUNNEL_LOG" 2>/dev/null; then
    HOST=$(curl -s "http://$METRICS/quicktunnel" | sed -n 's/.*"hostname":"\([^"]*\)".*/\1/p')
    [ -n "$HOST" ] && PUBLIC_URL="https://$HOST" && break
  fi
  sleep 1
done
[ -n "$PUBLIC_URL" ] || { echo "Туннель не поднялся, смотрите $TUNNEL_LOG"; exit 1; }
echo "    Адрес: $PUBLIC_URL"

echo "2/4 Записываю адрес в .env..."
sed "s|^PUBLIC_URL=.*|PUBLIC_URL=$PUBLIC_URL|" .env >.env.tmp && mv .env.tmp .env

echo "3/4 Запускаю проект (первый раз сборка займёт несколько минут)..."
docker compose up -d --build

echo "4/4 Подключаю бота к Telegram..."
docker compose run --rm bot-webhook

echo
echo "Готово."
echo "  Каталог в браузере: http://localhost:$HTTP_PORT"
echo "  Публичный адрес:    $PUBLIC_URL"
echo "  Остановить:         ./stop.sh"

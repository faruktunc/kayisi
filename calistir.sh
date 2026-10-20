#!/usr/bin/env bash
# Kayısı proses simülatörü — tak çalıştır.
#
#   ./calistir.sh            imajı (gerekirse) derle, başlat, tarayıcıda aç
#   ./calistir.sh durdur     konteyneri durdur ve kaldır
#   ./calistir.sh yeniden    imajı sıfırdan derleyip yeniden başlat (kod değiştiyse)
#   ./calistir.sh loglar     sunucu loglarını izle
#   ./calistir.sh durum      çalışıyor mu?
#   ./calistir.sh disa-aktar [dosya.tar.gz]   imajı internetsiz makineye taşımak için dosyaya yaz
#   ./calistir.sh ice-aktar  [dosya.tar.gz]   dosyadan imajı yükle
#
# Ortam değişkenleri: PORT (varsayılan 8080), ACMA=0 (tarayıcıyı açma)
set -euo pipefail

IMAGE="kayisi-simulator:latest"
CONTAINER="kayisi-simulator"
PORT="${PORT:-8080}"
ARCHIVE_DEFAULT="kayisi-simulator-image.tar.gz"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

info() { printf '\033[1;33m▶\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m✔\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m✘\033[0m %s\n' "$*" >&2; exit 1; }

# Çalışan bir Docker daemon'u varsa onu, yoksa Podman'ı kullan
detect_engine() {
  if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    ENGINE=docker
  elif command -v podman >/dev/null 2>&1; then
    ENGINE=podman
  elif command -v docker >/dev/null 2>&1; then
    fail "Docker kurulu ama daemon çalışmıyor. Başlatın: 'sudo systemctl start docker' (Linux) ya da Docker Desktop'ı açın."
  else
    fail "Docker ya da Podman bulunamadı. Kurulum: https://docs.docker.com/get-docker/"
  fi
}

image_exists()     { $ENGINE image inspect "$IMAGE" >/dev/null 2>&1; }
container_exists() { $ENGINE container inspect "$CONTAINER" >/dev/null 2>&1; }

build() {
  info "İmaj derleniyor ($ENGINE). İlk derleme birkaç dakika sürebilir…"
  local extra=()
  # Podman varsayılan OCI formatında HEALTHCHECK'i yok sayar
  [ "$ENGINE" = podman ] && extra=(--format docker)
  $ENGINE build "${extra[@]}" -t "$IMAGE" "$SCRIPT_DIR"
  ok "İmaj hazır: $IMAGE"
}

remove_container() {
  if container_exists; then
    $ENGINE rm -f "$CONTAINER" >/dev/null
  fi
}

port_in_use() {
  if command -v ss >/dev/null 2>&1; then
    ss -ltn 2>/dev/null | awk '{print $4}' | grep -Eq "[:.]${PORT}\$"
  elif command -v lsof >/dev/null 2>&1; then
    lsof -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1
  else
    return 1
  fi
}

wait_healthy() {
  local url="http://127.0.0.1:${PORT}/api/health"
  info "Sunucunun hazır olması bekleniyor…"
  for _ in $(seq 1 60); do
    if command -v curl >/dev/null 2>&1; then
      curl -fsS "$url" >/dev/null 2>&1 && return 0
    elif $ENGINE exec "$CONTAINER" python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2)" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  $ENGINE logs --tail 40 "$CONTAINER" >&2 || true
  fail "Sunucu 60 saniyede hazır olmadı (yukarıdaki loglara bakın)."
}

open_browser() {
  local url="http://localhost:${PORT}"
  [ "${ACMA:-1}" = "0" ] && return 0
  if command -v xdg-open >/dev/null 2>&1; then xdg-open "$url" >/dev/null 2>&1 &
  elif command -v open >/dev/null 2>&1; then open "$url"
  # Windows (Git Bash / WSL): Git Bash '/c' gibi argümanları yola çevirebildiği için cmd.exe yerine explorer.exe
  elif command -v explorer.exe >/dev/null 2>&1; then explorer.exe "$url" >/dev/null 2>&1 || true
  fi
}

start() {
  image_exists || build
  remove_container
  port_in_use && fail "Port ${PORT} kullanımda. Başka bir port deneyin: PORT=9090 ./calistir.sh"
  info "Konteyner başlatılıyor…"
  $ENGINE run -d --name "$CONTAINER" -p "${PORT}:8000" --restart unless-stopped "$IMAGE" >/dev/null
  wait_healthy
  ok "Çalışıyor: http://localhost:${PORT}"
  echo "   Durdurmak için: ./calistir.sh durdur"
  open_browser
}

stop() {
  if container_exists; then
    $ENGINE rm -f "$CONTAINER" >/dev/null
    ok "Durduruldu."
  else
    ok "Zaten çalışmıyor."
  fi
}

status() {
  if container_exists && [ "$($ENGINE container inspect -f '{{.State.Running}}' "$CONTAINER")" = "true" ]; then
    ok "Çalışıyor: http://localhost:$($ENGINE port "$CONTAINER" 8000 | head -1 | sed 's/.*://')"
  else
    echo "Çalışmıyor."
  fi
}

export_image() {
  local file="${1:-$ARCHIVE_DEFAULT}"
  image_exists || build
  info "İmaj dosyaya yazılıyor: $file"
  $ENGINE save "$IMAGE" | gzip > "$file"
  ok "Hazır ($(du -h "$file" | cut -f1)). Hedef makinede: ./calistir.sh ice-aktar $file && ./calistir.sh"
}

import_image() {
  local file="${1:-$ARCHIVE_DEFAULT}"
  [ -f "$file" ] || fail "Dosya bulunamadı: $file"
  info "İmaj yükleniyor: $file"
  local loaded name
  loaded="$(gunzip -c "$file" | $ENGINE load)"
  echo "$loaded"
  # Podman'da kaydedilen imaj 'localhost/...' adıyla gelir; Docker'da da bulunsun diye yeniden etiketle
  name="$(printf '%s\n' "$loaded" | sed -n 's/^Loaded image[^:]*: *//p' | tail -1)"
  if [ -n "$name" ] && [ "$name" != "$IMAGE" ]; then
    $ENGINE tag "$name" "$IMAGE"
  fi
  ok "İmaj yüklendi. Başlatmak için: ./calistir.sh"
}

detect_engine
case "${1:-baslat}" in
  baslat|start)       start ;;
  durdur|stop)        stop ;;
  yeniden|rebuild)    remove_container; build; start ;;
  loglar|logs)        $ENGINE logs -f "$CONTAINER" ;;
  durum|status)       status ;;
  disa-aktar|export)  export_image "${2:-}" ;;
  ice-aktar|import)   import_image "${2:-}" ;;
  -h|--help|yardim)   awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0" ;;
  *) fail "Bilinmeyen komut: $1 (yardım: ./calistir.sh yardim)" ;;
esac

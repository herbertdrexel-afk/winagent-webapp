#!/bin/bash
# Auf dem Server ausführen: bash deploy.sh
set -e

echo "==> Git pull..."
git pull origin master

echo "==> Docker images bauen und neu starten..."
docker compose build --pull
docker compose up -d --remove-orphans

echo "==> Fertig. Status:"
docker compose ps

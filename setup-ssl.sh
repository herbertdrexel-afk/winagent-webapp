#!/bin/bash
# SSL-Zertifikat für winagent.drexel.co.at einrichten
# Voraussetzung: DNS-A-Record winagent -> diese Server-IP ist bereits aktiv
set -e

DOMAIN="winagent.drexel.co.at"

echo "==> Certbot installieren..."
apt-get install -y certbot

echo "==> Port 80 kurz freigeben (Container stoppen)..."
docker compose stop frontend

echo "==> Zertifikat holen..."
certbot certonly --standalone -d "$DOMAIN" \
  --agree-tos --non-interactive \
  --email admin@drexel.co.at

echo "==> HTTPS-Nginx-Config schreiben..."
cat > frontend/nginx-ssl.conf << EOF
server {
    listen 80;
    server_name $DOMAIN;
    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl;
    server_name $DOMAIN;

    ssl_certificate     /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;

    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files \$uri \$uri/ /index.html;
    }

    location /api/ {
        proxy_pass         http://backend:8000/;
        proxy_set_header   Host              \$host;
        proxy_set_header   X-Real-IP         \$remote_addr;
        proxy_set_header   X-Forwarded-For   \$proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto \$scheme;
        proxy_read_timeout 60s;
    }
}
EOF

echo "==> docker-compose.yml um SSL-Port und Zertifikat erweitern..."
# Ports 80+443 und Letsencrypt-Volume in docker-compose.override.yml
cat > docker-compose.override.yml << EOF
services:
  frontend:
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /etc/letsencrypt:/etc/letsencrypt:ro
      - ./frontend/nginx-ssl.conf:/etc/nginx/conf.d/default.conf:ro
EOF

echo "==> Frontend neu starten mit SSL..."
docker compose up -d frontend

echo ""
echo "==> Fertig! https://$DOMAIN sollte jetzt erreichbar sein."
echo ""
echo "Zertifikat läuft nach 90 Tagen ab. Auto-Erneuerung einrichten:"
echo "  echo '0 3 * * * certbot renew --quiet && docker compose -f /opt/winagent/docker-compose.yml restart frontend' | crontab -"

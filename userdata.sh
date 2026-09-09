#!/bin/bash
apt-get update && apt-get install -y caddy gnupg
mkdir -p /etc/systemd/system/caddy.service.d
printf '[Service]\nEnvironmentFile=/etc/caddy/env\n' > /etc/systemd/system/caddy.service.d/env.conf
touch /etc/caddy/env
systemctl daemon-reload

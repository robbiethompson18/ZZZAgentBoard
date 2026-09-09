#!/bin/bash
# 512MB and no swap: apt alone can thrash the box into unreachability. Swap first.
fallocate -l 1G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile && echo '/swapfile none swap sw 0 0' >> /etc/fstab
systemctl stop snapd unattended-upgrades 2>/dev/null
apt-get update && apt-get install -y caddy gnupg
mkdir -p /etc/systemd/system/caddy.service.d
printf '[Service]\nEnvironmentFile=/etc/caddy/env\n' > /etc/systemd/system/caddy.service.d/env.conf
touch /etc/caddy/env
systemctl daemon-reload

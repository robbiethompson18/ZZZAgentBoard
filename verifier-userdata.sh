#!/bin/bash
# Verifier box first boot: docker, pinned Lean toolchain, formal-conjectures built at FC_COMMIT, foundry.
# `lake build` of formal-conjectures is the slow part (~1h on 2 vCPU). Progress: /var/log/cloud-init-output.log.
set -eu
FC_COMMIT=b82b08faa9006484021c12005ab41287fb2ffb69
fallocate -l 4G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile && echo '/swapfile none swap sw 0 0' >> /etc/fstab
apt-get update && apt-get install -y docker.io git curl python3-boto3
usermod -aG docker ubuntu
# Sandbox image: ubuntu + the one shared lib the Lean toolchain expects. Containers get no network, so nothing can be installed later.
printf 'FROM ubuntu:24.04\nRUN apt-get update && apt-get install -y --no-install-recommends libgmp10 && rm -rf /var/lib/apt/lists/*\n' | docker build -t zzz-sandbox -
sudo -u ubuntu bash -euc "
cd ~
curl -sSf https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh | sh -s -- -y --default-toolchain leanprover/lean4:v4.33.1
export PATH=\$HOME/.elan/bin:\$PATH
mkdir -p repos && git clone https://github.com/google-deepmind/formal-conjectures repos/formal-conjectures
cd repos/formal-conjectures && git checkout $FC_COMMIT
lake exe cache get && lake build
curl -L https://foundry.paradigm.xyz | bash && ~/.foundry/bin/foundryup
"
echo VERIFIER-READY

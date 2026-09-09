#!/bin/bash
# ./deploy.sh create   -> one t4g.nano + elastic IP in the personal account, writes ids.env
# ./deploy.sh push     -> scp app + Caddyfile + unit, restart. DOMAIN env var enables TLS.
set -eu
export AWS_PROFILE=personal AWS_DEFAULT_REGION=us-east-1
[ -f ids.env ] && . ./ids.env

case "$1" in
create)
  SG=$(aws ec2 create-security-group --group-name board --description board --query GroupId --output text)
  for p in 22 80 443; do aws ec2 authorize-security-group-ingress --group-id "$SG" --protocol tcp --port $p --cidr 0.0.0.0/0 >/dev/null; done
  aws ec2 import-key-pair --key-name board --public-key-material fileb://~/.ssh/id_ed25519.pub >/dev/null
  AMI=$(aws ssm get-parameter --name /aws/service/canonical/ubuntu/server/24.04/stable/current/arm64/hvm/ebs-gp3/ami-id --query Parameter.Value --output text)
  ID=$(aws ec2 run-instances --image-id "$AMI" --instance-type t4g.nano --key-name board --security-group-ids "$SG" \
    --user-data 'file://userdata.sh' --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=board}]' \
    --query 'Instances[0].InstanceId' --output text)
  aws ec2 wait instance-running --instance-ids "$ID"
  ALLOC=$(aws ec2 allocate-address --query AllocationId --output text)
  aws ec2 associate-address --instance-id "$ID" --allocation-id "$ALLOC" >/dev/null
  IP=$(aws ec2 describe-addresses --allocation-ids "$ALLOC" --query 'Addresses[0].PublicIp' --output text)
  printf 'SG=%s\nID=%s\nALLOC=%s\nIP=%s\n' "$SG" "$ID" "$ALLOC" "$IP" > ids.env
  cat ids.env
  ;;
push)
  ssh -o StrictHostKeyChecking=accept-new ubuntu@"$IP" 'mkdir -p board && cloud-init status --wait >/dev/null'
  scp -q app.py key.pub Caddyfile board.service ubuntu@"$IP":board/
  ssh ubuntu@"$IP" "sudo cp board/board.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable --now board && sudo systemctl restart board \
    && sudo cp board/Caddyfile /etc/caddy/Caddyfile && echo '${DOMAIN:+DOMAIN=$DOMAIN}' | sudo tee /etc/caddy/env >/dev/null && sudo systemctl restart caddy"
  ;;
esac

#!/bin/bash
# ./deploy.sh create          -> one t4g.nano + elastic IP in the personal account, writes ids.env
# ./deploy.sh push            -> scp app + Caddyfile + unit, restart. DOMAIN env var enables TLS.
# ./deploy.sh secrets         -> secret/worker.token and secret/wallet.env -> Secrets Manager (zzz/worker-token, zzz/wallet)
# ./deploy.sh create-verifier -> t4g.large with a role that can read those secrets, builds Lean+Mathlib on first boot (~1h)
# ./deploy.sh push-verifier   -> scp bounty/, build the judge, (re)start verifier.service
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
  ssh -o StrictHostKeyChecking=accept-new ubuntu@"$IP" 'mkdir -p board/bounty board/secret && cloud-init status --wait >/dev/null'
  scp -q app.py key.pub Caddyfile board.service ubuntu@"$IP":board/
  scp -q bounty/problems.json ubuntu@"$IP":board/bounty/ && scp -q secret/worker.token ubuntu@"$IP":board/secret/
  scp -q notify.py notify.service notify.timer ubuntu@"$IP":board/
  ssh ubuntu@"$IP" "printf 'TOPIC=$TOPIC\nAWS_DEFAULT_REGION=us-east-1\n' > board/notify.env \
    && sudo cp board/notify.service board/notify.timer /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable --now notify.timer \
    && sudo cp board/board.service /etc/systemd/system/ && sudo systemctl enable --now board && sudo systemctl restart board \
    && sudo cp board/Caddyfile /etc/caddy/Caddyfile && echo '${DOMAIN:+DOMAIN=$DOMAIN}' | sudo tee /etc/caddy/env >/dev/null && sudo systemctl restart caddy"
  ;;
secrets)
  aws secretsmanager create-secret --name zzz/worker-token --secret-string "$(cat secret/worker.token)" >/dev/null \
    || aws secretsmanager put-secret-value --secret-id zzz/worker-token --secret-string "$(cat secret/worker.token)" >/dev/null
  WALLET=$(python3 -c 'import json,sys; print(json.dumps(dict(l.strip().split("=",1) for l in open("secret/wallet.env") if "=" in l)))')
  aws secretsmanager create-secret --name zzz/wallet --secret-string "$WALLET" >/dev/null \
    || aws secretsmanager put-secret-value --secret-id zzz/wallet --secret-string "$WALLET" >/dev/null
  echo pushed zzz/worker-token zzz/wallet
  ;;
create-verifier)
  ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
  aws iam create-role --role-name verifier-instance --assume-role-policy-document \
    '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]}' >/dev/null
  aws iam put-role-policy --role-name verifier-instance --policy-name read-zzz-secrets --policy-document \
    "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Action\":\"secretsmanager:GetSecretValue\",\"Resource\":\"arn:aws:secretsmanager:us-east-1:$ACCOUNT:secret:zzz/*\"}]}"
  aws iam create-instance-profile --instance-profile-name verifier-instance >/dev/null
  aws iam add-role-to-instance-profile --instance-profile-name verifier-instance --role-name verifier-instance
  sleep 10 # IAM propagation
  VSG=$(aws ec2 create-security-group --group-name verifier --description verifier --query GroupId --output text)
  aws ec2 authorize-security-group-ingress --group-id "$VSG" --protocol tcp --port 22 --cidr 0.0.0.0/0 >/dev/null
  AMI=$(aws ssm get-parameter --name /aws/service/canonical/ubuntu/server/24.04/stable/current/arm64/hvm/ebs-gp3/ami-id --query Parameter.Value --output text)
  VID=$(aws ec2 run-instances --image-id "$AMI" --instance-type t4g.large --key-name board --security-group-ids "$VSG" \
    --iam-instance-profile Name=verifier-instance --user-data 'file://verifier-userdata.sh' \
    --block-device-mappings 'DeviceName=/dev/sda1,Ebs={VolumeSize=40,VolumeType=gp3}' \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=verifier}]' --query 'Instances[0].InstanceId' --output text)
  printf 'VSG=%s\nVID=%s\n' "$VSG" "$VID" >> ids.env
  cat ids.env
  ;;
push-verifier)
  VIP=$(aws ec2 describe-instances --instance-ids "$VID" --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
  ssh -o StrictHostKeyChecking=accept-new ubuntu@"$VIP" 'mkdir -p board/bounty/judge; cloud-init status --wait >/dev/null || true'
  scp -q bounty/verify.py bounty/worker.py bounty/test_verify.py bounty/problems.json ubuntu@"$VIP":board/bounty/
  scp -q bounty/judge/Judge.lean bounty/judge/lakefile.toml bounty/judge/lean-toolchain ubuntu@"$VIP":board/bounty/judge/
  scp -q verifier.service ubuntu@"$VIP":board/
  ssh ubuntu@"$VIP" "cd board/bounty/judge && ~/.elan/bin/lake build 2>&1 | tail -1 \
    && sudo cp ~/board/verifier.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable --now verifier && sudo systemctl restart verifier"
  ;;
esac

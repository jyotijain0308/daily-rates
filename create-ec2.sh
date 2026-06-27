#!/bin/bash
set -e

REGION="ap-south-1"
INSTANCE_NAME="flask-app"
KEY_NAME="flask-key"
SG_NAME="flask-sg"
VOLUME_SIZE=8

echo "Using region: $REGION"

# Ubuntu 24.04 AMI
AMI_ID=$(aws ssm get-parameter \
  --region "$REGION" \
  --name /aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id \
  --query "Parameter.Value" \
  --output text)

echo "AMI ID: $AMI_ID"

# Find free-tier eligible instance type
INSTANCE_TYPE=$(aws ec2 describe-instance-types \
  --region "$REGION" \
  --filters Name=free-tier-eligible,Values=true Name=processor-info.supported-architecture,Values=x86_64 \
  --query "InstanceTypes[?contains(InstanceType, 'micro') || contains(InstanceType, 'small')].InstanceType | [0]" \
  --output text)

if [ "$INSTANCE_TYPE" = "None" ] || [ -z "$INSTANCE_TYPE" ]; then
  echo "No x86_64 free-tier instance type found. Please check manually:"
  aws ec2 describe-instance-types \
    --region "$REGION" \
    --filters Name=free-tier-eligible,Values=true \
    --query "InstanceTypes[*].InstanceType" \
    --output table
  exit 1
fi

echo "Using instance type: $INSTANCE_TYPE"

# Create key pair if not exists
if aws ec2 describe-key-pairs --region "$REGION" --key-names "$KEY_NAME" >/dev/null 2>&1; then
  echo "Key pair already exists: $KEY_NAME"
else
  echo "Creating key pair: $KEY_NAME"
  aws ec2 create-key-pair \
    --region "$REGION" \
    --key-name "$KEY_NAME" \
    --query 'KeyMaterial' \
    --output text > "${KEY_NAME}.pem"

  chmod 400 "${KEY_NAME}.pem"
  echo "Private key saved as: ${KEY_NAME}.pem"
fi

# Create security group if not exists
SG_ID=$(aws ec2 describe-security-groups \
  --region "$REGION" \
  --filters Name=group-name,Values="$SG_NAME" \
  --query "SecurityGroups[0].GroupId" \
  --output text 2>/dev/null || true)

if [ "$SG_ID" = "None" ] || [ -z "$SG_ID" ]; then
  echo "Creating security group: $SG_NAME"

  SG_ID=$(aws ec2 create-security-group \
    --region "$REGION" \
    --group-name "$SG_NAME" \
    --description "Security group for Flask Docker app" \
    --query "GroupId" \
    --output text)
fi

echo "Security Group ID: $SG_ID"

# Get current public IP for SSH
MY_IP=$(curl -s https://checkip.amazonaws.com)

echo "Allowing SSH from: ${MY_IP}/32"

# Add ingress rules safely
aws ec2 authorize-security-group-ingress \
  --region "$REGION" \
  --group-id "$SG_ID" \
  --protocol tcp \
  --port 22 \
  --cidr "${MY_IP}/32" 2>/dev/null || true

aws ec2 authorize-security-group-ingress \
  --region "$REGION" \
  --group-id "$SG_ID" \
  --protocol tcp \
  --port 80 \
  --cidr 0.0.0.0/0 2>/dev/null || true

aws ec2 authorize-security-group-ingress \
  --region "$REGION" \
  --group-id "$SG_ID" \
  --protocol tcp \
  --port 443 \
  --cidr 0.0.0.0/0 2>/dev/null || true

# Launch instance
echo "Launching EC2 instance..."

INSTANCE_ID=$(aws ec2 run-instances \
  --region "$REGION" \
  --image-id "$AMI_ID" \
  --instance-type "$INSTANCE_TYPE" \
  --key-name "$KEY_NAME" \
  --security-group-ids "$SG_ID" \
  --block-device-mappings "[{\"DeviceName\":\"/dev/sda1\",\"Ebs\":{\"VolumeSize\":$VOLUME_SIZE,\"VolumeType\":\"gp3\",\"DeleteOnTermination\":true}}]" \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$INSTANCE_NAME}]" \
  --query "Instances[0].InstanceId" \
  --output text)

echo "Instance ID: $INSTANCE_ID"
echo "Waiting for instance to run..."

aws ec2 wait instance-running \
  --region "$REGION" \
  --instance-ids "$INSTANCE_ID"

PUBLIC_IP=$(aws ec2 describe-instances \
  --region "$REGION" \
  --instance-ids "$INSTANCE_ID" \
  --query "Reservations[0].Instances[0].PublicIpAddress" \
  --output text)

echo ""
echo "EC2 instance created successfully!"
echo "Instance ID: $INSTANCE_ID"
echo "Public IP: $PUBLIC_IP"
echo "SSH command:"
echo "ssh -i ${KEY_NAME}.pem ubuntu@$PUBLIC_IP"
echo ""
echo "To download key from CloudShell:"
echo "Actions → Download file → ${KEY_NAME}.pem"
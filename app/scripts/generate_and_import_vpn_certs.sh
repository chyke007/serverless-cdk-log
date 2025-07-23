#!/bin/bash
set -e

# ---- CONFIG ----
AWS_REGION="us-east-1"
DOMAIN="serverlessvpn"

# ---- GENERATE CERTIFICATES ----
mkdir -p vpn-certs && cd vpn-certs

echo "Generating Root CA..."
openssl genrsa -out clientvpn-rootCA.key 2048
openssl req -x509 -new -nodes -key clientvpn-rootCA.key -sha256 -days 3650 -out clientvpn-rootCA.crt -subj "/CN=ClientVPN-RootCA"

echo "Generating Server Certificate..."
openssl genrsa -out clientvpn-server.key 2048
openssl req -new -key clientvpn-server.key -out clientvpn-server.csr -subj "/CN=server.${DOMAIN}"
openssl x509 -req -in clientvpn-server.csr -CA clientvpn-rootCA.crt -CAkey clientvpn-rootCA.key -CAcreateserial -out clientvpn-server.crt -days 3650 -sha256

echo "Generating Client Certificate..."
openssl genrsa -out clientvpn-client.key 2048
openssl req -new -key clientvpn-client.key -out clientvpn-client.csr -subj "/CN=client.${DOMAIN}"
openssl x509 -req -in clientvpn-client.csr -CA clientvpn-rootCA.crt -CAkey clientvpn-rootCA.key -CAcreateserial -out clientvpn-client.crt -days 3650 -sha256

# ---- IMPORT TO ACM ----
echo "Importing Server Certificate to ACM..."
SERVER_CERT_ARN=$(aws acm import-certificate \
  --certificate fileb://clientvpn-server.crt \
  --private-key fileb://clientvpn-server.key \
  --certificate-chain fileb://clientvpn-rootCA.crt \
  --region $AWS_REGION \
  --query CertificateArn --output text)

echo "Importing Client Root CA to ACM..."
CLIENT_CERT_ARN=$(aws acm import-certificate \
  --certificate fileb://clientvpn-rootCA.crt \
  --private-key fileb://clientvpn-rootCA.key \
  --region $AWS_REGION \
  --query CertificateArn --output text)

echo "----"
echo "Server Certificate ARN: $SERVER_CERT_ARN"
echo "Client Root CA ARN:     $CLIENT_CERT_ARN"
echo "----"
echo "Use these ARNs in your CDK deployment:"
echo "  cdk deploy -c vpn_server_cert_arn=$SERVER_CERT_ARN -c vpn_client_cert_arn=$CLIENT_CERT_ARN"
echo "----"
echo "Distribute these files to VPN users:"
echo "  clientvpn-client.crt, clientvpn-client.key, clientvpn-rootCA.crt" 

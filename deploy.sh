#!/bin/bash
# =============================================================================
# CloudComply AI — EC2 Deploy Script
# Run this ONCE on a fresh Ubuntu EC2 instance.
# Prerequisites: port 80 and 8000 open in Security Group.
# =============================================================================
set -e

echo "=== [1/6] Installing Docker ==="
sudo apt-get update -y
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update -y
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

echo "=== [2/6] Adding current user to docker group ==="
sudo usermod -aG docker $USER

echo "=== [3/6] Installing Git ==="
sudo apt-get install -y git

echo "=== [4/6] Cloning repository ==="
# Replace this URL with your actual repo URL
git clone https://github.com/abhi2808/CloudComply-Investigator_AI_Agent.git /home/ubuntu/cloudcomply
cd /home/ubuntu/cloudcomply

echo "=== [5/6] Setting up environment ==="
echo ""
echo ">>> ACTION REQUIRED <<<"
echo "Create the .env file with your production values."
echo "Run:  nano /home/ubuntu/cloudcomply/.env"
echo "Then paste and fill in all values from .env.production"
echo ""
echo "Once done, press ENTER to continue..."
read -r

echo "=== [6/6] Building and starting containers ==="
cd /home/ubuntu/cloudcomply
sudo docker compose up --build -d

echo ""
echo "============================================================"
echo " CloudComply AI is now running!"
echo " Frontend: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)"
echo " Backend:  http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):8000/docs"
echo "============================================================"
echo ""
echo "IMPORTANT: Update your Azure Bot Messaging Endpoint to:"
echo "  https://YOUR_DOMAIN_OR_IP/api/messages"
echo "(Port 80 must be open. For HTTPS you need a domain + SSL cert)"

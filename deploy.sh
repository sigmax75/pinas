#!/bin/bash
# PiNAS Deploy Script - run on Orange Pi after SCP upload
# Usage: bash deploy.sh

echo "=== PiNAS Deploy ==="

cd /home/orangepi

if [ ! -f deploy.zip ]; then
    echo "[ERROR] deploy.zip not found in /home/orangepi/"
    echo "Upload it via SCP first."
    exit 1
fi

# Stop running server
echo "Stopping server..."
pkill -f "uvicorn app:app" 2>/dev/null
sleep 1

# Backup current
echo "Backing up current..."
if [ -d pinas/web ]; then
    cp -r pinas/web pinas/web_backup_$(date +%Y%m%d_%H%M%S)
fi

# Extract
echo "Extracting..."
mkdir -p pinas_deploy
unzip -o deploy.zip -d pinas_deploy

# Copy files
echo "Deploying..."
cp -r pinas_deploy/web/* pinas/web/ 2>/dev/null
cp pinas_deploy/archive.sh pinas/ 2>/dev/null
cp pinas_deploy/archive.conf pinas/ 2>/dev/null

# Cleanup
rm -rf pinas_deploy deploy.zip

# Install dependencies if needed
pip3 install python-multipart 2>/dev/null

echo "=== Deploy complete ==="
echo ""
echo "Start server with:"
echo "  cd ~/pinas/web && python3 -m uvicorn app:app --host 0.0.0.0 --port 8080"
echo ""
echo "Or run in background:"
echo "  cd ~/pinas/web && nohup python3 -m uvicorn app:app --host 0.0.0.0 --port 8080 > /tmp/pinas.log 2>&1 &"

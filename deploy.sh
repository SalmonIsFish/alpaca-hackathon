#!/bin/bash
# Deployment script for DigitalOcean server
# Usage: ./deploy.sh

set -e  # Exit on error

echo "=========================================="
echo "Amanah Trader - Deployment Script"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if we're in the right directory
if [ ! -f "web_app.py" ]; then
    echo -e "${RED}Error: web_app.py not found${NC}"
    echo "Please run this script from the project root directory"
    exit 1
fi

# Configuration - UPDATE THESE BEFORE RUNNING
SERVER_IP="YOUR_SERVER_IP_HERE"
SERVER_USER="amanah"
PROJECT_DIR="/home/amanah/alpaca-hackathon"
REMOTE_URL="https://amanahtrader.uk/dashboard/"

echo -e "${YELLOW}Configuration:${NC}"
echo "  Server: $SERVER_IP"
echo "  User: $SERVER_USER"
echo "  Project: $PROJECT_DIR"
echo "  URL: $REMOTE_URL"
echo ""

# Step 1: Create deployment package
echo -e "${GREEN}Step 1: Creating deployment package...${NC}"
mkdir -p deploy
cp -r agent deploy/
cp -r data deploy/
cp -r logs deploy/
cp web_app.py deploy/
cp wsgi.py deploy/
cp requirements.txt deploy/
cp run_scheduler.py deploy/
cp agent/scheduler.py deploy/ 2>/dev/null || true
cp check_status.py deploy/ 2>/dev/null || true
cp -r tests deploy/ 2>/dev/null || true
touch deploy/logs/decisions.jsonl

echo -e "${GREEN}✓ Package created${NC}"
echo ""

# Step 2: Create .env template
echo -e "${GREEN}Step 2: Creating .env template...${NC}"
cat > deploy/.env << 'EOF'
# Alpaca Configuration
ALPACA_PROFILE=dedicated
ALPACA_LIVE_TRADE=false

# Featherless LLM
FEATHERLESS_API_KEY=your_api_key_here
FEATHERLESS_MODEL=Qwen/Qwen3.8-27B

# Paths
SHARIAH_UNIVERSE_PATH=data/shariah_universe.json
DECISIONS_LOG_PATH=logs/decisions.jsonl

# Risk Limits
MAX_ORDERS_PER_DAY=3
MAX_POSITION_PCT=40
MAX_DAILY_LOSS_PCT=3
EOF

echo -e "${GREEN}✓ .env template created${NC}"
echo ""

# Step 3: Create systemd service file
echo -e "${GREEN}Step 3: Creating systemd service...${NC}"
cat > deploy/amanahtrader.service << EOF
[Unit]
Description=Amanah Trader - Autonomous AI Trading Agent
After=network.target

[Service]
Type=simple
User=$SERVER_USER
WorkingDirectory=$PROJECT_DIR
Environment=PATH=$PROJECT_DIR/venv/bin
Environment=PYTHONPATH=$PROJECT_DIR
Environment=FLASK_APP=web_app.py
ExecStart=$PROJECT_DIR/venv/bin/gunicorn -w 2 -b 127.0.0.1:8000 wsgi:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

echo -e "${GREEN}✓ Service file created${NC}"
echo ""

# Step 4: Create scheduler service
echo -e "${GREEN}Step 4: Creating scheduler service...${NC}"
cat > deploy/amanahtrader-scheduler.service << EOF
[Unit]
Description=Amanah Trader Scheduler
After=network.target

[Service]
Type=simple
User=$SERVER_USER
WorkingDirectory=$PROJECT_DIR
Environment=PATH=$PROJECT_DIR/venv/bin
ExecStart=$PROJECT_DIR/venv/bin/python $PROJECT_DIR/run_scheduler.py --start --interval 60
Restart=always
RestartSec=60

[Install]
WantedBy=multi-user.target
EOF

echo -e "${GREEN}✓ Scheduler service created${NC}"
echo ""

# Step 5: Create nginx config
echo -e "${GREEN}Step 5: Creating nginx config...${NC}"
cat > deploy/nginx-amanahtrader << 'EOF'
server {
    listen 80;
    server_name amanahtrader.uk www.amanahtrader.uk;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static {
        alias /home/amanah/alpaca-hackathon/static;
        expires 30d;
    }
}
EOF

echo -e "${GREEN}✓ Nginx config created${NC}"
echo ""

# Step 6: Create remote setup script
echo -e "${GREEN}Step 6: Creating remote setup script...${NC}"
cat > deploy/setup_remote.sh << 'EOF'
#!/bin/bash
# Run this on the server after deployment

set -e

echo "Setting up Amanah Trader on server..."

# Create virtual environment
cd /home/amanah/alpaca-hackathon
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Install gunicorn
pip install gunicorn

# Create logs directory if not exists
mkdir -p logs

# Set permissions
chmod +x run_scheduler.py
chmod +x check_status.py

echo "Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env with your credentials"
echo "2. Configure Alpaca CLI: alpaca profile login --name dedicated"
echo "3. Test: python check_status.py"
echo "4. Start services: sudo systemctl start amanahtrader amanahtrader-scheduler"
EOF

chmod +x deploy/setup_remote.sh

echo -e "${GREEN}✓ Remote setup script created${NC}"
echo ""

# Step 7: Create deployment instructions
echo -e "${GREEN}Step 7: Creating deployment instructions...${NC}"
cat > deploy/DEPLOY_INSTRUCTIONS.txt << EOF
DEPLOYMENT INSTRUCTIONS
========================

Local Machine (Before SSH):
---------------------------
1. Copy .env file to deploy/ directory with real credentials
   cp .env deploy/.env

2. Update deploy.sh with your actual server IP:
   SERVER_IP="your_actual_ip_here"

3. Make sure you can SSH to the server:
   ssh amanah@\$SERVER_IP

Deployment:
-----------
4. Run deployment:
   ./deploy.sh

5. Copy to server:
   scp -r deploy/* amanah@\$SERVER_IP:/home/amanah/alpaca-hackathon/

On Server (SSH):
---------------
6. SSH to server:
   ssh amanah@\$SERVER_IP

7. Run setup:
   cd /home/amanah/alpaca-hackathon
   ./setup_remote.sh

8. Configure services:
   sudo cp amanahtrader.service /etc/systemd/system/
   sudo cp amanahtrader-scheduler.service /etc/systemd/system/
   sudo cp nginx-amanahtrader /etc/nginx/sites-available/
   sudo ln -sf /etc/nginx/sites-available/nginx-amanahtrader /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl reload nginx

9. Start services:
   sudo systemctl daemon-reload
   sudo systemctl enable amanahtrader amanahtrader-scheduler
   sudo systemctl start amanahtrader amanahtrader-scheduler

10. Test:
    curl http://localhost:8000/
    python check_status.py

Monitoring:
-----------
- View logs: sudo journalctl -u amanahtrader -f
- View scheduler: sudo journalctl -u amanahtrader-scheduler -f
- Check status: python check_status.py
- Web interface: https://amanahtrader.uk/dashboard/

Troubleshooting:
----------------
If web interface doesn't load:
  - Check nginx: sudo systemctl status nginx
  - Check app: sudo systemctl status amanahtrader
  - Check firewall: sudo ufw status
  - Check logs: sudo journalctl -u amanahtrader

If scheduler not trading:
  - Check scheduler: sudo systemctl status amanahtrader-scheduler
  - Check logs: sudo journalctl -u amanahtrader-scheduler
  - Test manually: python -m agent.pipeline --dry-run

Emergency Stop:
---------------
Stop trading: sudo systemctl stop amanahtrader-scheduler
Stop web: sudo systemctl stop amanahtrader
Stop all: sudo systemctl stop amanahtrader amanahtrader-scheduler
EOF

echo -e "${GREEN}✓ Instructions created${NC}"
echo ""

# Summary
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment Package Ready!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Files created in deploy/:"
ls -1 deploy/
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Copy your .env file to deploy/.env"
echo "2. Update SERVER_IP in deploy.sh"
echo "3. Read deploy/DEPLOY_INSTRUCTIONS.txt"
echo "4. Run: ./deploy.sh"
echo "5. Copy to server and follow instructions"
echo ""
echo -e "${GREEN}Good luck! 🚀${NC}"

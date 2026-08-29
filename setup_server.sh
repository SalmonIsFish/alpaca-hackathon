#!/bin/bash
# Server setup script for Alpaca CLI and autonomous trading
# Run this on the server after deploying the code

echo "=========================================="
echo "Amanah Trader - Server Setup"
echo "=========================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Setup directory
HACKATHON_DIR="/home/amanah/hackathon"
cd "$HACKATHON_DIR" || exit 1

echo -e "${GREEN}Step 1: Setting up Python Alpaca CLI...${NC}"

# Make alpaca executable
chmod +x alpaca
chmod +x alpaca_cli.py

# Create symlink in /usr/local/bin for easy access
sudo ln -sf "$HACKATHON_DIR/alpaca" /usr/local/bin/alpaca-hackathon

echo -e "${GREEN}✓ Python Alpaca CLI ready${NC}"
echo ""

echo -e "${YELLOW}Step 2: API Key Configuration${NC}"
echo "You need to provide Alpaca API credentials."
echo "Get them from: https://alpaca.markets/")
echo ""

# Check if .env exists and has credentials
if [ -f .env ]; then
    if grep -q "ALPACA_API_KEY" .env && grep -q "ALPACA_SECRET_KEY" .env; then
        echo -e "${GREEN}✓ API keys found in .env${NC}"
    else
        echo -e "${YELLOW}⚠ API keys not found in .env${NC}"
        echo "Please add these lines to .env:"
        echo "ALPACA_API_KEY=your_api_key_here"
        echo "ALPACA_SECRET_KEY=your_secret_key_here"
    fi
else
    echo -e "${RED}✗ .env file not found${NC}"
    echo "Creating .env template..."
    cat > .env << 'EOF'
# Alpaca API Keys (Get from https://alpaca.markets/)
ALPACA_API_KEY=your_api_key_here
ALPACA_SECRET_KEY=your_secret_key_here

# Or use OAuth profile
ALPACA_PROFILE=testing

# Featherless LLM
FEATHERLESS_API_KEY=your_featherless_key_here
FEATHERLESS_MODEL=Qwen/Qwen3.8-27B

# Paths
SHARIAH_UNIVERSE_PATH=data/shariah_universe_enhanced.json
DECISIONS_LOG_PATH=logs/decisions.jsonl

# Risk Limits
MAX_ORDERS_PER_DAY=3
MAX_POSITION_PCT=40
MAX_DAILY_LOSS_PCT=3
EOF
    echo -e "${YELLOW}⚠ Created .env template - please edit with your credentials${NC}"
fi

echo ""
echo -e "${GREEN}Step 3: Testing connectivity...${NC}"

# Test with API keys if available
if grep -q "ALPACA_API_KEY=" .env && ! grep -q "your_api_key" .env; then
    export $(grep -v '^#' .env | xargs)
    if python3 alpaca_cli.py doctor 2>/dev/null | grep -q "All checks passed"; then
        echo -e "${GREEN}✓ API connection successful${NC}"
    else
        echo -e "${YELLOW}⚠ API connection failed - check your keys${NC}"
    fi
else
    echo -e "${YELLOW}⚠ Skipping API test - no keys configured${NC}"
fi

echo ""
echo -e "${GREEN}Step 4: Setting up scheduler service...${NC}"

# Create systemd service for scheduler
sudo tee /etc/systemd/system/hackathon-scheduler.service > /dev/null << 'EOF'
[Unit]
Description=Amanah Trader Hackathon Scheduler
After=network.target

[Service]
Type=simple
User=amanah
WorkingDirectory=/home/amanah/hackathon
Environment=PYTHONPATH=/home/amanah/hackathon
# Load env vars from .env
EnvironmentFile=/home/amanah/hackathon/.env
ExecStart=/usr/bin/python3 /home/amanah/hackathon/agent/scheduler.py
Restart=always
RestartSec=60

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
echo -e "${GREEN}✓ Scheduler service created${NC}"

echo ""
echo -e "${GREEN}Step 5: Setting up web app service...${NC}"

# Update web app service
sudo tee /etc/systemd/system/hackathon-app.service > /dev/null << 'EOF'
[Unit]
Description=Amanah Trader Hackathon Web App
After=network.target

[Service]
Type=simple
User=amanah
WorkingDirectory=/home/amanah/hackathon
Environment=PYTHONPATH=/home/amanah/hackathon
EnvironmentFile=/home/amanah/hackathon/.env
ExecStart=/usr/bin/python3 /home/amanah/hackathon/wsgi.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable hackathon-app
echo -e "${GREEN}✓ Web app service configured${NC}"

echo ""
echo "=========================================="
echo "SETUP COMPLETE"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Edit .env with your Alpaca API keys"
echo "2. Test: ./alpaca doctor"
echo "3. Start scheduler: sudo systemctl start hackathon-scheduler"
echo "4. Check status: sudo systemctl status hackathon-scheduler"
echo ""
echo "Application URL: https://amanahtrader.uk/hackathon/"
echo ""

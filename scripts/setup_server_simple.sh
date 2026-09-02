#!/bin/bash
# Simple server setup script

echo "Setting up Amanah Trader on server..."
cd /home/amanah/hackathon

# Make scripts executable
chmod +x alpaca alpaca_cli.py

# Create symlink
sudo ln -sf /home/amanah/hackathon/alpaca /usr/local/bin/alpaca-hackathon

# Check .env
if [ -f .env ]; then
    echo ".env found"
    if grep -q "ALPACA_API_KEY=" .env; then
        echo "API keys configured"
    else
        echo "Please add API keys to .env"
    fi
else
    echo "Creating .env template..."
    cat > .env << 'EOF'
ALPACA_API_KEY=your_api_key_here
ALPACA_SECRET_KEY=your_secret_key_here
FEATHERLESS_API_KEY=your_featherless_key_here
FEATHERLESS_MODEL=Qwen/Qwen3.8-27B
SHARIAH_UNIVERSE_PATH=data/shariah_universe_enhanced.json
DECISIONS_LOG_PATH=logs/decisions.jsonl
MAX_ORDERS_PER_DAY=3
MAX_POSITION_PCT=40
MAX_DAILY_LOSS_PCT=3
EOF
fi

# Create scheduler service
sudo tee /etc/systemd/system/hackathon-scheduler.service > /dev/null << 'EOF'
[Unit]
Description=Hackathon Scheduler
After=network.target

[Service]
Type=simple
User=amanah
WorkingDirectory=/home/amanah/hackathon
Environment=PYTHONPATH=/home/amanah/hackathon
EnvironmentFile=/home/amanah/hackathon/.env
ExecStart=/usr/bin/python3 -m agent.scheduler
Restart=always
RestartSec=60

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
echo "Setup complete!"
echo ""
echo "Next:"
echo "1. Edit .env with your Alpaca API keys"
echo "2. Run: ./alpaca doctor"
echo "3. Start: sudo systemctl start hackathon-scheduler"

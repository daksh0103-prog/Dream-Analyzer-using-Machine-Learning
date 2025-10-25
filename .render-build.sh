#!/usr/bin/env bash
# Force Render to use a specific Python version before installing dependencies

set -o errexit

echo "🔧 Forcing Python 3.11.9 setup..."

# Install Python 3.11 using deadsnakes PPA (Render build system uses Ubuntu)
apt-get update -y
apt-get install -y python3.11 python3.11-venv python3.11-distutils

# Point 'python3' to the installed Python 3.11
update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
update-alternatives --set python3 /usr/bin/python3.11

echo "✅ Python version now set to: $(python3 --version)"

# Upgrade pip for safety
python3 -m pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

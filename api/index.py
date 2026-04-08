import sys
import os

# Add parent directory so app.py, database.py, ai_model.py are importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app

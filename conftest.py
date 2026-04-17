import sys
from pathlib import Path

# Make the project root importable so `from src.X import ...` works in tests
sys.path.insert(0, str(Path(__file__).parent))

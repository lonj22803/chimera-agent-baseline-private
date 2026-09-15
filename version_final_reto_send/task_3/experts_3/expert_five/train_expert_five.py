"""Entrena y mide con el protocolo compartido del paso 5.3."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "train"))
from protocol import main

if __name__ == "__main__":
    main()

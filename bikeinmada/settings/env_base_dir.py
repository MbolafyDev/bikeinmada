# zarastore/settings/env_base_dir.py
from pathlib import Path
import os

# Détection auto : si prod, prend 3 niveaux, sinon 2
ENV = os.getenv("ENV", "local")
if ENV == "production":
    BASE_DIR = Path(__file__).resolve().parent.parent.parent
else:
    BASE_DIR = Path(__file__).resolve().parent.parent.parent

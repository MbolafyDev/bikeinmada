import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# First load a generic .env (for fallback)
default_env_file = BASE_DIR.parent / ".env"
load_dotenv(default_env_file)

# Now read ENV to decide which real .env file to load
env = os.getenv("ENV", "local")  # default to 'local'

if env == "production":
    env_file = BASE_DIR.parent / ".env.prod"
elif env == "dev":
    env_file = BASE_DIR.parent / ".env.dev"
else:
    env_file = default_env_file

# Re-load selected .env file to overwrite
load_dotenv(env_file, override=True)

# Finally, load the actual Django settings
if env == "production":
    from .prod import *
else:
    from .dev import *

print(f"🔧 Using settings environment: {env}")

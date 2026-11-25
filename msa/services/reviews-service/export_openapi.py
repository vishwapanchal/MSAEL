"""Write msa/api/reviews-openapi.yaml from the FastAPI app (needs PyYAML: requirements-dev.txt)."""
import os
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from app.main import app  # noqa: E402

OUT = os.path.normpath(os.path.join(HERE, "..", "..", "api", "reviews-openapi.yaml"))

if __name__ == "__main__":
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        yaml.safe_dump(app.openapi(), f, sort_keys=False)
    print("wrote", OUT)

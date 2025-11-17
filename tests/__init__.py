import sys
from pathlib import Path

src_path = Path(__file__).resolve().parents[1] / "src"
if str(src_path) not in sys.path:
    sys.path.append(str(src_path))


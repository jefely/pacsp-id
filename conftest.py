"""Make the repository's own modules importable in tests without installing.

scripts/ holds the pipeline modules (pacsp_build, pacsp_innov, ...) and
experiments/transient is the 瞬在 package. Adding both to sys.path keeps
`pytest` working straight from a clone.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent
for rel in ("scripts", "experiments"):
    p = ROOT / rel
    if p.is_dir() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

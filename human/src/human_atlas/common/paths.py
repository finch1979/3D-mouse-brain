"""Shared filesystem paths for the human_atlas package.

Every build script needs to resolve the same species-root-relative
locations (outputs/, data/cache/, and the repo-shared web/lib/); centralizing
that here means moving a script deeper into the package tree doesn't break
its path math.
"""

from pathlib import Path

# human/src/human_atlas/common/paths.py -> human/
SPECIES_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = SPECIES_ROOT.parent

DATA_DIR = SPECIES_ROOT / "data"
DATA_CACHE_DIR = DATA_DIR / "cache"
OUTPUTS_DIR = SPECIES_ROOT / "outputs"

WEB_LIB_DIR = REPO_ROOT / "web" / "lib"
EXTERNAL_DIR = REPO_ROOT / "external"

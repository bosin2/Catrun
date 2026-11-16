"""Compatibility entry point for the floorplan panel's current migration."""

from pathlib import Path
import sys

import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT / 'Scripts/Menu'))

from author_minimap_hold_neighborhood import main


if __name__ == '__main__':
    main('-catrunminimapprojectionaudit')

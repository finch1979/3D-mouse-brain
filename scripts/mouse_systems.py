"""Use this checkout's mouse package even if a different copy is pip-installed.

Fetch only: py -3.13 scripts/mouse_systems.py fetch
Build all:  py -3.13 scripts/mouse_systems.py build
Build one:  py -3.13 scripts/mouse_systems.py build auditory
"""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'mouse' / 'src'))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['fetch','build'])
    parser.add_argument('system',nargs='?',default='all')
    args=parser.parse_args()
    if args.action=='fetch':
        from mouse_atlas.fetch.atlas_3d import main as fetch
        sys.argv=[sys.argv[0],'--systems']
        fetch()
    else:
        from mouse_atlas.build.adult_system import main as build
        from mouse_atlas.build.systems import SYSTEMS
        if args.system not in ['all',*SYSTEMS]:
            parser.error('Unknown system: '+args.system)
        build(args.system)


if __name__=='__main__':
    main()

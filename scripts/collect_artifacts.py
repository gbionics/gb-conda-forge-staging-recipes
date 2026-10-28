"""Keep channel subdirectories intact and publish noarch from x86-64 only.

Both runners build and test noarch against their native dependencies. Selecting
one copy prevents architecture jobs from overwriting the same noarch artifact.
"""
import argparse
import shutil
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('platform', choices=('linux-64', 'linux-aarch64'))
platform = parser.parse_args().platform
subdirs = [platform, 'noarch'] if platform == 'linux-64' else [platform]
for subdir in subdirs:
    packages = sorted((Path('output') / subdir).glob('*.conda'))
    if not packages:
        raise SystemExit(f'No packages found in output/{subdir}')
    destination = Path('artifacts') / subdir
    destination.mkdir(parents=True, exist_ok=True)
    for package in packages:
        shutil.copy2(package, destination / package.name)

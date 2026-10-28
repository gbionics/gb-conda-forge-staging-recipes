"""Publish only on main, under the trusted publisher's production identity."""
import os
import subprocess
from pathlib import Path

if not (
    os.environ.get('GITHUB_ACTIONS') == 'true'
    and os.environ.get('GITHUB_REPOSITORY') == 'gbionics/gb-conda-forge-staging-recipes'
    and os.environ.get('GITHUB_REF') == 'refs/heads/main'
    and os.environ.get('GITHUB_EVENT_NAME') in ('push', 'workflow_dispatch')
):
    raise SystemExit('Uploads require a main-branch GitHub Actions run.')
packages = sorted(
    package
    for subdir in ('linux-64', 'linux-aarch64', 'noarch')
    for package in (Path('output') / subdir).glob('*.conda')
)
if not packages:
    raise SystemExit('No packages to upload.')
subprocess.run([
    'rattler-build', 'upload', 'prefix', '--channel', '@gbionics/conda-forge-staging',
    '--skip-existing', *map(str, packages),
], check=True)

"""Build the stack using local artifacts and compatible conda-forge variants."""
import argparse
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
order = ('hpipm', 'tera-renderer', 'acados')
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--recipe', choices=order, action='append', help='Build only selected recipes (repeatable).')
selected = parser.parse_args().recipe or order
for recipe in order:
    if recipe not in selected:
        continue
    subprocess.run([
        'rattler-build', 'build', '--recipe', str(root / 'recipes' / recipe),
        '--variant-config', str(root / 'conda_forge_pinnings/conda_build_config.yaml'),
        '--output-dir', str(root / 'output'),
        '-c', (root / 'output').as_uri(),
        '-c', 'conda-forge',
    ], check=True, cwd=root)

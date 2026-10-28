"""Select migrations whose relevant dependency feedstocks have finished building."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from staging.pinning import render_pinning, update_pinning
from staging.recipe_dependencies import dependencies_from_recipes

version, migrations, reports = update_pinning(
    'pinning.yaml', platforms=('linux-64', 'linux-aarch64'),
    dependencies=dependencies_from_recipes(Path('recipes')),
)
render_pinning('pinning.yaml', 'conda_forge_pinnings/conda_build_config.yaml')
print(f'conda-forge-pinning: {version}; migrations: {migrations}')
for name, report in reports:
    print(f'{name}: {report}')

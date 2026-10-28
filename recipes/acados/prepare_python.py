"""Synchronize release metadata and explicitly include all codegen resources."""
import os
import re
from pathlib import Path

p = Path('setup.py')
s = p.read_text()
s = re.sub(r"version='[^']*'", f"version='{os.environ['PKG_VERSION']}'", s, count=1)
s = re.sub(r"\s*setup_requires=\[[^]]*\],", '', s)
s = re.sub(r"\s*use_scm_version=\{.*?\},", '', s, flags=re.S)
# matplotlib-base supplies the Python matplotlib distribution.
p.write_text(s)
# A manifest includes nested ROS templates, .pyx/.pxd, and future template files.
resources = [str(p) for p in Path('acados_template').rglob('*')
             if p.is_file() and p.suffix != '.pyc']
Path('MANIFEST.in').write_text(''.join(f'include {p}\n' for p in resources))

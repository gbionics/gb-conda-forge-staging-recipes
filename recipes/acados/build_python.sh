#!/usr/bin/env bash
set -euxo pipefail
cd interfaces/acados_template
"$PYTHON" "$RECIPE_DIR/prepare_python.py"
"$PYTHON" -m pip install . --no-deps --no-build-isolation --no-compile -vv

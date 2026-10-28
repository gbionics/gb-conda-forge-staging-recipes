#!/usr/bin/env bash
set -euxo pipefail
export CARGO_HOME="$SRC_DIR/.cargo"
cp "$RECIPE_DIR/Cargo.lock" Cargo.lock
cp "$RECIPE_DIR/LICENSE" LICENSE
cargo-bundle-licenses --format yaml --output THIRDPARTY.yml
cargo install --locked --no-track --root "$PREFIX" --path .

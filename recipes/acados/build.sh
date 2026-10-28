#!/usr/bin/env bash
set -euxo pipefail
cmake ${CMAKE_ARGS:-} -S . -B build -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$PREFIX" \
  -DCMAKE_INSTALL_LIBDIR=lib -DBUILD_SHARED_LIBS=ON \
  -DCMAKE_FIND_PACKAGE_TARGETS_GLOBAL=ON \
  -DACADOS_WITH_SYSTEM_BLASFEO=ON -DACADOS_WITH_SYSTEM_HPIPM=ON \
  -DACADOS_WITH_OPENMP=OFF -DACADOS_EXAMPLES=ON -DACADOS_UNIT_TESTS=OFF \
  -DACADOS_WITH_QPOASES=OFF -DACADOS_WITH_OSQP=OFF -DACADOS_WITH_DAQP=OFF
cmake --build build --parallel "${CPU_COUNT:-2}"
ctest --test-dir build --output-on-failure --no-tests=error
cmake --install build
install -m 0644 lib/link_libs.json "$PREFIX/lib/link_libs.json"
# Tarball builds have no .git directory. Record the release rather than UNKNOWN.
printf 'v%s\n' "$ACADOS_VERSION" > "$PREFIX/lib/git_commit_hash"

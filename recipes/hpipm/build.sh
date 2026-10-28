#!/usr/bin/env bash
set -euxo pipefail
# The upstream export file needs BLASFEO to be loaded before its targets.
cmake ${CMAKE_ARGS:-} -S . -B build -G Ninja \
  -DCMAKE_INSTALL_PREFIX="$PREFIX" -DCMAKE_BUILD_TYPE=Release \
  -DHPIPM_FIND_BLASFEO=ON -DBUILD_SHARED_LIBS=ON \
  -DTARGET="$HPIPM_TARGET" -DHPIPM_TESTING=ON
cmake --build build --parallel "${CPU_COUNT:-2}"
# This revision builds test executables but does not register CTest tests.
for name in d_cond d_part_cond d_dense_qp d_ocp_qp d_tree_ocp_qp; do
  "build/test_problems/$name" > "$name.log"
done
cmake --install build
mv "$PREFIX/cmake/hpipmConfig.cmake" "$PREFIX/cmake/hpipmTargets.cmake"
sed -i 's/hpipmConfig-/hpipmTargets-/g' "$PREFIX/cmake/hpipmTargets.cmake"
cat > "$PREFIX/cmake/hpipmConfig.cmake" <<'CMAKE'
include(CMakeFindDependencyMacro)
find_dependency(blasfeo)
include("${CMAKE_CURRENT_LIST_DIR}/hpipmTargets.cmake")
CMAKE
# CMake's export loader locates the per-configuration files by basename.
for path in "$PREFIX"/cmake/hpipmConfig-*.cmake; do
  mv "$path" "${path/hpipmConfig-/hpipmTargets-}"
done

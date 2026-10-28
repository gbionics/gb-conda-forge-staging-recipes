Pinning rendering, migration selection, variant algebra, and recipe dependency
inspection are adapted from gbionics/rock-the-conda (BSD-3-Clause; see LICENSE),
using the same conda-forge base + completed migrations + overrides pattern as
RoboStack/robostack. The updater supplies dependencies from this repository rather
than requiring downloaded feedstocks. Preserve selector and zip_keys semantics.

Original module source revision (local checkout when adapted):
f880afb1070c9761e0c185b84d76084a6e2fea74

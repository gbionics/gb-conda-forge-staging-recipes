# conda-forge-staging-recipes

Recipes for packages intended for conda-forge, published to
[gbionics/conda-forge-staging](https://prefix.dev/channels/@gbionics/conda-forge-staging).

## Build and test

Install [Pixi](https://pixi.sh), then run:

```sh
pixi install --locked
pixi run test
pixi run build
# Optional: rebuild selected recipes in dependency order
pixi run build --recipe hpipm --recipe acados
```

The committed `pixi.lock` locks packaging tools. The committed
`conda_forge_pinnings/conda_build_config.yaml` supplies compiler and dependency
variants; building does not fetch a moving pinning configuration. Packages are
built and tested in order, with `output/` ahead of conda-forge in channel priority.
BLASFEO is supplied by conda-forge, including its executable-stack fix:

| Recipe | Package | Source |
| --- | --- | --- |
| hpipm | libhpipm + libhpipm-devel 0.1.4 | upstream release tag `0.1.4` |
| tera-renderer | tera-renderer 0.2.1 (`t_renderer`) | acados 0.6.0's renderer revision `a480a64` |
| acados | libacados + libacados-devel + acados-template 0.6.0 | shared upstream release, external HPIPM and BLASFEO |

Recipes allow any Linux architecture; CI builds **Linux x86-64 and Linux aarch64**
on native `ubuntu-24.04` and `ubuntu-24.04-arm` runners. Other Linux platforms
can build once their dependencies are available, but are not tested here.

HPIPM and the native acados outputs each have a recipe-local microarchitecture
matrix in their own `conda_build_config.yaml`: x86-64 levels 1 and 3. HPIPM uses
`GENERIC` at level 1 and `AVX` at level 3; other architectures use `GENERIC`.
Acados links the matching HPIPM/BLASFEO family at each level. Build numbers prefer
level 3 on capable machines, while `_x86_64-microarch-level` protects older CPUs.
`acados-template` remains one noarch output; tera-renderer builds once per platform.

HPIPM's own `GENERIC`/`AVX` choice changes implementation, not public structures.
However, BLASFEO's targets can change its packed-matrix ABI: `X64_INTEL_CORE`
(level 1) uses single-precision panel size 4, while `X64_INTEL_HASWELL` (level 3)
uses 8; both use double-precision panel size 4. HPIPM directly indexes both layouts.
See upstream [block sizes](https://github.com/giaf/blasfeo/blob/0.1.4.3/include/blasfeo_block_size.h),
[matrix access macros](https://github.com/giaf/blasfeo/blob/0.1.4.3/include/blasfeo_common.h),
and [HPIPM target selection](https://github.com/giaf/hpipm/blob/0.1.4/CMakeLists.txt).

Each HPIPM x86-64 variant builds against the matching BLASFEO variant:
level 1 requires `libblasfeo * *_10*`, and level 3 requires `libblasfeo * *_30*`.
These build-string constraints are also exported to consumers, together with
the BLASFEO version range resolved at build time. They permit compatible
rebuilds without locking a complete build string. This is a workaround assuming
fewer than nine builds per BLASFEO version; the layout ABI should instead be
represented by a `libblasfeo-abi` package or similar.

Both native acados variants use matching HPIPM and BLASFEO build families and
propagate that requirement to consumers. The Python output depends on the native
package version without selecting a CPU variant, so the solver can choose the
appropriate native pair. Other Linux architectures have no x86 build-string
constraint. Both BLASFEO variants come from conda-forge; the temporary local
recipe was removed after the executable-stack fix was merged upstream.

A small HPIPM patch initializes the equality-constraint backup count before
restore; the upstream dense-QP test exposed an uninitialized read. Optional QP
backends and OpenMP are disabled. The Python package is noarch, but requires a
Linux native stack. Its runtime dependencies include the compilers, make, and
CMake needed to compile generated solvers. Deployments of precompiled solvers can
depend only on `libacados`.

`libhpipm-devel` and `libacados-devel` collect headers, CMake files, and any
static libraries, pkg-config files, and documentation, with exact dependencies
on their runtime outputs.
Both use the same generic file patterns; their existing root `cmake/` layout is
preserved through the additional `cmake/**` pattern. `acados-template` depends on
`libacados-devel`, which brings in `libhpipm-devel` for runtime code generation.

`tera-renderer` uses a committed Cargo.lock and bundles Rust dependency licenses.
Its BSD-2-Clause license is assumed to match acados, as requested for this
staging repository; `recipes/tera-renderer/LICENSE` records that license text.

## CI and publishing

`.github/workflows/build-pkgs.yml` builds and tests the entire stack for every
PR and push to main on both native architectures. Each runner builds the stack (ten packages on x86-64, six on aarch64)
and tests code generation, cached solvers, Cython, and simulation.
Architecture-specific packages are retained in separate Actions artifacts. Only
the x86-64 artifact contributes the noarch package when publishing; ARM still
builds and tests its copy. After a successful main build, a separate `publish` job uploads those
same artifacts using prefix.dev OIDC trusted publishing:

- Owner/repository: `gbionics/gb-conda-forge-staging-recipes`
- Workflow file: `build-pkgs.yml`
- GitHub environment: `production`
- Channel: `@gbionics/conda-forge-staging`
- Access: read/write, all packages

Configure a prefix.dev OIDC trusted publisher for the repository, workflow,
`production` environment, and staging channel listed above. No API key secret is
needed. PR build jobs have no OIDC write permission and never publish. Manual
main-branch runs can publish too. Existing identical artifacts are skipped;
increment a recipe's build number when changing its packaging without changing
its version.

## Pinning and dependency updates

Following [RoboStack/robostack](https://github.com/RoboStack/robostack/tree/main/shared/pinning)
and [gbionics/rock-the-conda](https://github.com/gbionics/rock-the-conda),
`pinning.yaml` records an exact conda-forge-pinning version, applied migrations,
and local overrides. The renderer preserves selectors and zipped variants.
The implementation is adapted from rock-the-conda; its BSD-3-Clause license is
in `staging/LICENSE`.

```sh
pixi run pinning-render   # reproduce the generated file from the exact base
pixi run pinning-update   # select a new base and completed relevant migrations
pixi update              # refresh packaging tools, including their lockfile
pixi run test
pixi run build
```

The updater considers both Linux architectures, discovers dependencies in the recipes, maps package names to
feedstocks, and consults conda-forge migration status. It waits for all relevant
participating dependency feedstocks to finish, ignores paused/inapplicable
migrations, and retains already applied migrations and deliberate overrides.
Weekly CI opens an update PR after building the candidate stack. It builds in
the updater itself because PRs created with GITHUB_TOKEN do not trigger PR CI.
Repository Actions settings must allow Actions to create pull requests.
Package source revisions and Cargo.lock are reviewed updates: when upgrading
acados, review HPIPM release compatibility, update the renderer revision, and
rerun the integration tests.

## Integration tests

The installed-package test controls a nonlinear three-zone thermal system with
three temperature states and two heating/cooling inputs. It uses discrete
dynamics, NONLINEAR_LS costs at initial/intermediate/terminal stages, SQP_RTI,
PARTIAL_CONDENSING_HPIPM, ROBUST mode, and soft nonlinear temperature constraints.
It updates setpoints, cost weights, state/input bounds, and slack penalties;
checks numerical solutions; reloads cached solvers without generation or
compilation; and builds the Cython wrapper. A separate first-order thermal
simulation is checked against its analytic solution.

Tests run under Python 3.12 and 3.13 with NumPy `>=2,<2.3`, without source-layout
environment variables or `LD_LIBRARY_PATH`, and with Python network access
blocked. Both native CPU variants also run upstream numerical examples and CMake
consumer checks.

Install `acados-template` from the staging channel to use code generation and
runtime compilation. The package locates resources relative to itself and native
libraries relative to `sys.prefix`; it does not download renderer binaries
automatically. Rebuild cached generated solvers when changing the native ABI
family or upgrading the solver stack.

Recipe references: [HPIPM PR #33975](https://github.com/conda-forge/staged-recipes/pull/33975)
and [acados PR #33818](https://github.com/conda-forge/staged-recipes/pull/33818).

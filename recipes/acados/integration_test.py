"""Offline code generation for a nonlinear three-zone thermal control problem.

Exercise soft constraints, parameter updates, cached solvers, Cython, and a
separate first-order thermal simulation using only installed packages.
"""
import os
import sys
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

# No activation hooks or source checkout may be needed.
for name in ('ACADOS_SOURCE_DIR', 'ACADOS_PYTHON_INTERFACE_PATH', 'TERA_PATH', 'LD_LIBRARY_PATH'):
    os.environ.pop(name, None)

import casadi as cs
import numpy as np
from acados_template import AcadosModel, AcadosOcp, AcadosOcpSolver, AcadosSim, AcadosSimSolver, sim_get_default_cmake_builder
from acados_template.utils import get_acados_path, get_python_interface_path, get_tera


def make_ocp():
    ocp = AcadosOcp()
    model = ocp.model
    model.name = 'thermal_network_smoke'
    model.x = cs.SX.sym('temperature', 3)
    model.u = cs.SX.sym('heat_input', 2)
    model.p = cs.SX.sym('temperature_reference', 3)
    t1, t2, t3 = cs.vertsplit(model.x)
    heat_flow = cs.vertcat(
        -0.6 * t1 + 0.15 * t2 + model.u[0],
        0.15 * t1 - 0.5 * t2 + 0.1 * t3 - 0.05 * t2**3 + model.u[1],
        0.1 * t2 - 0.35 * t3 + 0.25 * model.u[0],
    )
    model.disc_dyn_expr = model.x + 0.1 * heat_flow
    model.cost_y_expr = cs.vertcat(model.x - model.p, model.u)
    model.cost_y_expr_0 = model.cost_y_expr
    model.cost_y_expr_e = model.x - model.p
    # Soft limits on temperature energy and inter-zone temperature differences.
    model.con_h_expr = cs.vertcat(t1**2 + 0.5 * t3**2, (t2 - t3)**2)
    model.con_h_expr_e = model.con_h_expr
    for suffix, size in (('_0', 5), ('', 5), ('_e', 3)):
        setattr(ocp.cost, 'cost_type' + suffix, 'NONLINEAR_LS')
        setattr(ocp.cost, 'W' + suffix, np.eye(size))
        setattr(ocp.cost, 'yref' + suffix, np.zeros(size))
    for suffix in ('', '_e'):
        setattr(ocp.constraints, 'lh' + suffix, np.zeros(2))
        setattr(ocp.constraints, 'uh' + suffix, np.array([1.6, 1.2]))
        setattr(ocp.constraints, 'idxsh' + suffix, np.arange(2))
        for name in ('zl', 'zu', 'Zl', 'Zu'):
            setattr(ocp.cost, name + suffix, np.ones(2))
        setattr(ocp.constraints, 'idxbx' + suffix, np.arange(3))
        setattr(ocp.constraints, 'lbx' + suffix, -np.ones(3) * 2)
        setattr(ocp.constraints, 'ubx' + suffix, np.ones(3) * 2)
    ocp.constraints.x0 = np.array([0.6, -0.4, 0.3])
    ocp.constraints.idxbu = np.arange(2)
    ocp.constraints.lbu = -np.ones(2)
    ocp.constraints.ubu = np.ones(2)
    ocp.parameter_values = np.zeros(3)
    opts = ocp.solver_options
    opts.N_horizon = 12
    opts.tf = 1.2
    opts.nlp_solver_type = 'SQP_RTI'
    opts.qp_solver = 'PARTIAL_CONDENSING_HPIPM'
    opts.qp_solver_iter_max = 50
    opts.hessian_approx = 'GAUSS_NEWTON'
    opts.integrator_type = 'DISCRETE'
    opts.levenberg_marquardt = 1e-3
    opts.hpipm_mode = 'ROBUST'
    ocp.code_export_directory = str(Path.cwd() / 'cached_solver')
    return ocp


def exercise_mpc(solver):
    x0 = np.array([0.6, -0.4, 0.3])
    for k in range(13):
        solver.set(k, 'p', np.zeros(3))
        solver.cost_set(k, 'W', np.diag([12., 16., 10.]) if k == 12 else np.diag([6., 8., 5., 1.2, 1.2]))
        solver.cost_set(k, 'yref', np.zeros(3 if k == 12 else 5))
        solver.set(k, 'x', x0)
        if k < 12:
            solver.set(k, 'u', np.zeros(2))
            solver.constraints_set(k, 'lbu', -np.ones(2))
            solver.constraints_set(k, 'ubu', np.ones(2))
        if k > 0:
            solver.constraints_set(k, 'lh', np.zeros(2))
            solver.constraints_set(k, 'uh', np.array([1.6, 1.2]))
            solver.constraints_set(k, 'lbx', -np.ones(3) * 2)
            solver.constraints_set(k, 'ubx', np.ones(3) * 2)
            for name in ('zl', 'zu', 'Zl', 'Zu'):
                solver.cost_set(k, name, np.ones(2) * 100)
    # Repeat control updates with fixed initial measurements.
    for _ in range(4):
        solver.constraints_set(0, 'lbx', x0)
        solver.constraints_set(0, 'ubx', x0)
        assert solver.solve() == 0
    u = solver.get(0, 'u')
    assert np.isfinite(u).all() and np.max(np.abs(u)) <= 1.00001, u
    assert np.dot(x0[:2], u) < 0, (x0, u)
    trajectory = np.array([solver.get(k, 'x') for k in range(13)])
    assert np.isfinite(trajectory).all()
    assert np.linalg.norm(trajectory[-1]) < np.linalg.norm(x0)
    # Parameter update must change control without regenerating or recompiling.
    for k in range(13):
        solver.set(k, 'p', np.array([0.8, -0.6, 0.5]))
    for _ in range(4):
        assert solver.solve() == 0
    assert np.linalg.norm(solver.get(0, 'u') - u) > 0.1


def check_simulation():
    sim = AcadosSim()
    m = AcadosModel()
    m.name = 'thermal_response_smoke'
    m.x = cs.SX.sym('x')
    m.u = cs.SX.sym('u')
    m.xdot = cs.SX.sym('xdot')
    m.f_expl_expr = -0.4 * m.x + 0.8 * m.u
    m.f_impl_expr = m.xdot - m.f_expl_expr
    sim.model = m
    sim.solver_options.T = 0.1
    sim.solver_options.integrator_type = 'ERK'
    sim.code_export_directory = str(Path.cwd() / 'sim_solver')
    builder = sim_get_default_cmake_builder()
    builder.additional_cmake_options = ''
    solver = AcadosSimSolver(sim, json_file=str(Path.cwd() / 'sim.json'),
                             cmake_builder=builder, verbose=False)
    solver.set('x', np.array([0.2]))
    solver.set('u', np.array([0.3]))
    assert solver.solve() == 0
    expected_temperature = 0.6 + (0.2 - 0.6) * np.exp(-0.4 * 0.1)
    np.testing.assert_allclose(solver.get('x'), [expected_temperature], atol=1e-10)


def main():
    assert Path(get_acados_path()).resolve() == Path(sys.prefix).resolve()
    for tool in ('cc', 'c++', 'make', 'cmake', 'cython'):
        assert Path(shutil.which(tool)).resolve().is_relative_to(Path(sys.prefix).resolve()), tool
    interface = Path(get_python_interface_path())
    assert (interface / 'acados_ocp_solver_pyx.pyx').is_file()
    assert list((interface / 'ros2_templates').rglob('*.in.*'))
    # Fail any attempted in-process network access, even if codegen regresses.
    with patch('socket.socket.connect', side_effect=AssertionError('offline test')):
        assert Path(get_tera()).is_file()
        ocp = make_ocp()
        json_path = str(Path.cwd() / 'acados_ocp.json')
        solver = AcadosOcpSolver(ocp, json_file=json_path, verbose=False)
        exercise_mpc(solver)
        del solver
        # Reload the generated solver without generation or compilation.
        cached = AcadosOcpSolver(ocp, json_file=json_path, generate=False, build=False, verbose=False)
        exercise_mpc(cached)
        del cached
        cython_solver = AcadosOcpSolver.create_cython_solver(ocp, generate=False, build=True, verbose=True)
        exercise_mpc(cython_solver)
        check_simulation()
    print('Installed offline MPC, cache reload, Cython, and simulation checks passed.')


if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='acados-installed-') as work:
        os.chdir(work)
        main()

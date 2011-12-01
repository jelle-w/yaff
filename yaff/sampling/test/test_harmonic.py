# YAFF is yet another force-field code
# Copyright (C) 2008 - 2011 Toon Verstraelen <Toon.Verstraelen@UGent.be>, Center
# for Molecular Modeling (CMM), Ghent University, Ghent, Belgium; all rights
# reserved unless otherwise stated.
#
# This file is part of YAFF.
#
# YAFF is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 3
# of the License, or (at your option) any later version.
#
# YAFF is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>
#
# --


import numpy as np

from yaff import *
from yaff.sampling.test.common import get_ff_water32, get_ff_water, get_ff_bks


def test_hessian_partial_water32():
    ff = get_ff_water32()
    select = [1, 2, 3, 14, 15, 16]
    hessian = estimate_cart_hessian(ff, select=select)
    assert hessian.shape == (18, 18)


def test_hessian_full_water():
    ff = get_ff_water()
    hessian = estimate_cart_hessian(ff)
    assert hessian.shape == (9, 9)
    evals = np.linalg.eigvalsh(hessian)
    print evals
    assert sum(abs(evals) < 1e-10) == 3


def test_elastic_water32():
    ff = get_ff_water32()
    elastic = estimate_elastic(ff, do_frozen=True)
    assert elastic.shape == (6, 6)


def test_bulk_elastic_bks():
    ff = get_ff_bks(smooth_ei=True, reci_ei='ignore')
    system = ff.system
    lcs = np.array([
        [1, 1, 0],
        [0, 0, 1],
    ])
    system.align_cell(lcs)
    ff.update_rvecs(system.cell.rvecs)
    opt = BFGSOptimizer(FullCellDOF(ff))
    opt.run()
    rvecs0 = system.cell.rvecs.copy()
    vol0 = system.cell.volume
    pos0 = system.pos.copy()
    e0 = ff.compute()
    elastic = estimate_elastic(ff)
    assert abs(pos0 - system.pos).max() < 1e-10
    assert abs(rvecs0 - system.cell.rvecs).max() < 1e-10
    assert abs(vol0 - system.cell.volume) < 1e-10
    assert elastic.shape == (6, 6)
    # Make estimates of the same matrix elements with a simplistic approach
    eps = 1e-3
    # A) stretch in the Z direction
    deform = np.array([1, 1, 1-eps])
    rvecs1 = rvecs0*deform
    pos1 = pos0*deform
    ff.update_rvecs(rvecs1)
    opt = BFGSOptimizer(CartesianDOF(ff))
    opt.run()
    e1 = ff.compute()
    deform = np.array([1, 1, 1+eps])
    rvecs2 = rvecs0*deform
    pos2 = pos0*deform
    ff.update_rvecs(rvecs2)
    opt = BFGSOptimizer(CartesianDOF(ff))
    opt.run()
    e2 = ff.compute()
    C = (e1 + e2 - 2*e0)/(eps**2)/vol0
    # B) stretch in the X direction
    deform = np.array([1-eps, 1, 1])
    rvecs1 = rvecs0*deform
    pos1 = pos0*deform
    ff.update_rvecs(rvecs1)
    opt = BFGSOptimizer(CartesianDOF(ff))
    opt.run()
    e1 = ff.compute()
    deform = np.array([1+eps, 1, 1])
    rvecs2 = rvecs0*deform
    pos2 = pos0*deform
    ff.update_rvecs(rvecs2)
    opt = BFGSOptimizer(CartesianDOF(ff))
    opt.run()
    e2 = ff.compute()
    C = (e1 + e2 - 2*e0)/(eps**2)/vol0
    assert abs(C - elastic[0,0]) < C*0.01
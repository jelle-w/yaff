# -*- coding: utf-8 -*-
# YAFF is yet another force-field code.
# Copyright (C) 2011 Toon Verstraelen <Toon.Verstraelen@UGent.be>,
# Louis Vanduyfhuys <Louis.Vanduyfhuys@UGent.be>, Center for Molecular Modeling
# (CMM), Ghent University, Ghent, Belgium; all rights reserved unless otherwise
# stated.
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


from __future__ import division
from __future__ import print_function

import numpy as np
import pkg_resources

from yaff import *
from molmod.units import angstrom
from molmod import MolecularGraph, bond_length

from yaff.pes.test.common import check_gpos_cv_fd, check_vtens_cv_fd
from yaff.test.common import get_system_quartz


def test_cvvolume_quartz():
    system = get_system_quartz()
    cv = CVVolume(system)
    value = cv.compute()
    assert np.abs(value-np.abs(np.linalg.det(system.cell.rvecs)))<1e-10
    check_gpos_cv_fd(cv)
    check_vtens_cv_fd(cv)


def test_cvcomprojection_mof5():
    # Load the system
    fn_system = pkg_resources.resource_filename(__name__, '../../data/test/system_mof5.chk')
    system = System.from_file(fn_system)
    # Groups that define the COM
    atypes = set(['C_B', 'C_B_BR_O', 'O_p', 'B_p','C_HTTP', 'C_O_BR_O', 'C_O'])
    graph = MolecularGraph(system.bonds, system.numbers)
    indices = graph.independent_vertices
    groups = []
    for layer in [0,1]:
        groups.append( [iatom for iatom in indices[layer] if system.get_ffatype(iatom) in atypes] )
    # Compute the COMs explicitly
    coms = [(system.pos[group]*system.masses[group].reshape((-1,1))).sum(axis=0)/system.masses[group].sum() for group in groups]
    relcom = coms[1]-coms[0]
    # Loop over different projections
    for index in range(3):
        # Compute using the CollectiveVariable
        cv = CVCOMProjection(system, groups, index)
        value = cv.compute()
        # Compute the projection vector
        a,b,c = system.cell.rvecs[0],system.cell.rvecs[1],system.cell.rvecs[2]
        if index==0:
            u = a.copy()
        elif index==1:
            u = np.cross(np.cross(a,b),a)
        elif index==2:
            u = np.cross(a,b)
        u/=np.linalg.norm(u)
        cv_ref = np.dot(relcom,u)
        assert np.abs(cv_ref-value)<1e-3
        # Check derivatives
        check_gpos_cv_fd(cv)
        check_vtens_cv_fd(cv)


def test_cvinternalcoordinate_quartz():
    system = get_system_quartz()
    ic = Bond(1,3)
    cv = CVInternalCoordinate(system, ic)
    value = cv.compute()
    assert value==cv.get_last_computed_value()
    delta = system.pos[3]-system.pos[1]
    system.cell.mic(delta)
    reference = bond_length([np.zeros(3, float), delta])[0]
    assert np.abs(value-reference)<1e-8
    check_gpos_cv_fd(cv)
    check_vtens_cv_fd(cv)


def test_cvlincombic_quartz():
    system = get_system_quartz()
    ic0 = Bond(1,3)
    ic1 = Bond(2,5)
    weights = [0.13,0.29]
    cv = CVLinCombIC(system, [ic0,ic1], weights)
    value = cv.compute()
    assert value==cv.get_last_computed_value()
    delta0 = system.pos[3]-system.pos[1]
    system.cell.mic(delta0)
    ref0 = bond_length([np.zeros(3, float), delta0])[0]
    delta1 = system.pos[5]-system.pos[2]
    system.cell.mic(delta1)
    ref1 = bond_length([np.zeros(3, float), delta1])[0]
    reference = weights[0]*ref0+weights[1]*ref1
    assert np.abs(value-reference)<1e-8
    check_gpos_cv_fd(cv)
    check_vtens_cv_fd(cv)

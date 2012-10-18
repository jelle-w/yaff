# -*- coding: utf-8 -*-
# YAFF is yet another force-field code
# Copyright (C) 2011 - 2012 Toon Verstraelen <Toon.Verstraelen@UGent.be>,
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
#--

# TODO: change import style: h5py as h5

import shutil, os, h5py, numpy as np

from yaff import *
from yaff.analysis.test.common import get_nve_water32
from yaff.sampling.test.common import get_ff_water32


def test_rdf1_offline():
    dn_tmp, nve, f = get_nve_water32()
    try:
        select = nve.ff.system.get_indexes('O')
        rdf = RDF(4.5*angstrom, 0.1*angstrom, f, select0=select)
        print f['trajectory'].keys()
        assert 'trajectory/pos_rdf' in f
        assert 'trajectory/pos_rdf/d' in f
        assert 'trajectory/pos_rdf/counts' in f
        assert 'trajectory/pos_rdf/rdf' in f
        assert 'trajectory/pos_rdf/crdf' in f
        fn_png = '%s/rdf.png' % dn_tmp
        rdf.plot(fn_png)
        assert os.path.isfile(fn_png)
        fn_png = '%s/crdf.png' % dn_tmp
        rdf.plot_crdf(fn_png)
        assert os.path.isfile(fn_png)
    finally:
        shutil.rmtree(dn_tmp)
        f.close()


def test_rdf1_online():
    # Setup a test FF
    ff = get_ff_water32()
    # Run a test simulation
    f = h5py.File('test_rdf1_online.h5', driver='core', backing_store=False)
    try:
        hdf5 = HDF5Writer(f)
        select = ff.system.get_indexes('O')
        rdf0 = RDF(4.5*angstrom, 0.1*angstrom, f, select0=select)
        nve = NVEIntegrator(ff, 1.0*femtosecond, hooks=[hdf5, rdf0])
        nve.run(5)
        assert nve.counter == 5
        # Also run an off-line rdf and compare
        rdf1 = RDF(4.5*angstrom, 0.1*angstrom, f, select0=select)
        assert rdf0.nsample == rdf1.nsample
        assert abs(rdf0.d - rdf1.d).max() < 1e-10
        assert abs(rdf0.rdf - rdf1.rdf).max() < 1e-10
        assert abs(rdf0.crdf - rdf1.crdf).max() < 1e-10
        assert abs(rdf0.counts - rdf1.counts).max() < 1e-10
    finally:
        f.close()


def test_rdf2_offline():
    dn_tmp, nve, f = get_nve_water32()
    try:
        select0 = nve.ff.system.get_indexes('O')
        select1 = nve.ff.system.get_indexes('H')
        rdf = RDF(4.5*angstrom, 0.1*angstrom, f, select0=select0, select1=select1)
        assert 'trajectory/pos_rdf' in f
        assert 'trajectory/pos_rdf/d' in f
        assert 'trajectory/pos_rdf/counts' in f
        assert 'trajectory/pos_rdf/rdf' in f
        assert 'trajectory/pos_rdf/crdf' in f
        fn_png = '%s/rdf.png' % dn_tmp
        rdf.plot(fn_png)
        assert os.path.isfile(fn_png)
    finally:
        shutil.rmtree(dn_tmp)
        f.close()


def test_rdf2_online():
    # Setup a test FF
    ff = get_ff_water32()
    # Run a test simulation
    f = h5py.File('test_rdf2_online.h5', driver='core', backing_store=False)
    try:
        hdf5 = HDF5Writer(f)
        select0 = ff.system.get_indexes('O')
        select1 = ff.system.get_indexes('H')
        rdf0 = RDF(4.5*angstrom, 0.1*angstrom, f, select0=select0, select1=select1)
        nve = NVEIntegrator(ff, 1.0*femtosecond, hooks=[hdf5, rdf0])
        nve.run(5)
        assert nve.counter == 5
        # Also run an off-line rdf and compare
        rdf1 = RDF(4.5*angstrom, 0.1*angstrom, f, select0=select0, select1=select1)
        assert rdf0.nsample == rdf1.nsample
        assert abs(rdf0.d - rdf1.d).max() < 1e-10
        assert abs(rdf0.rdf - rdf1.rdf).max() < 1e-10
        assert abs(rdf0.crdf - rdf1.crdf).max() < 1e-10
        assert abs(rdf0.counts - rdf1.counts).max() < 1e-10
    finally:
        f.close()


def test_rdf2_online_blind():
    # Setup a test FF and run simulation without any HDF5 file
    ff = get_ff_water32()
    select0 = ff.system.get_indexes('O')
    select1 = ff.system.get_indexes('H')
    rdf = RDF(4.5*angstrom, 0.1*angstrom, select0=select0, select1=select1)
    nve = NVEIntegrator(ff, 1.0*femtosecond, hooks=rdf)
    nve.run(5)
    assert nve.counter == 5
    assert rdf.nsample == 6


def test_rdf2_offline_exclude():
    dn_tmp, nve, f = get_nve_water32()
    try:
        select0 = nve.ff.system.get_indexes('O')
        select1 = nve.ff.system.get_indexes('H')
        exclude = []
        for i in xrange(32):
            exclude.append((3*i+1,3*i))
            exclude.append((3*i+2,3*i))
        exclude = np.array(exclude)
        rdf = RDF(4.5*angstrom, 0.1*angstrom, f, select0=select0, select1=select1, exclude=exclude)
        assert 'trajectory/pos_rdf' in f
        assert 'trajectory/pos_rdf/d' in f
        assert 'trajectory/pos_rdf/counts' in f
        assert 'trajectory/pos_rdf/rdf' in f
        assert 'trajectory/pos_rdf/crdf' in f
        fn_png = '%s/rdf.png' % dn_tmp
        rdf.plot(fn_png)
        assert os.path.isfile(fn_png)
    finally:
        shutil.rmtree(dn_tmp)
        f.close()


def test_rdf_from_file_variable_cell():
    system = System.from_file('input/chloro_pos.xyz', rvecs=np.diag([48.877]*3))
    with h5py.File('test_rdf_from_file_variable_cell.h5', driver='core', backing_store=False) as f:
        # Prepare in-memory HDF5 file
        system.to_hdf5(f)
        xyz_to_hdf5(f, 'input/chloro_pos.xyz')
        rvecs_traj = []
        with file('input/chloro_vol.txt') as fvol:
            for line in fvol:
                if line.startswith(' INITIAL'):
                    vol = float(line.split()[3])
                else:
                    vol = float(line.split()[2])
                rvecs = np.identity(3, float)*vol**(1.0/3.0)
                rvecs_traj.append(rvecs)
        rvecs_traj = np.array(rvecs_traj)
        f['trajectory']['cell'] = rvecs_traj

        # run the analysis
        select0 = system.get_indexes('6')
        rdf = RDF(10.0*angstrom, 0.5*angstrom, f, select0=select0, cellpath='trajectory/cell')

        # do some tests
        assert 'trajectory/pos_rdf' in f
        assert 'trajectory/pos_rdf/d' in f
        assert 'trajectory/pos_rdf/counts' in f
        assert 'trajectory/pos_rdf/rdf' in f
        assert 'trajectory/pos_rdf/crdf' in f
        # The first part of the RDF should be zero.
        assert (rdf.rdf[:6] == 0.0).all()

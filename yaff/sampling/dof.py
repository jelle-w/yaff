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
"""Convenient Wrappers for the ForceField object

   All these class are called DOF classes, because they specify a set of degrees
   of freedom.
"""


import numpy as np

from molmod.minimizer import check_delta


__all__ = [
    'DOF', 'CartesianDOF', 'BaseCellDOF', 'FullCellDOF', 'IsoCellDOF',
    'AnisoCellDOF'
]


class DOF(object):
    def __init__(self, ff):
        """
           **Arguments:**

           ff
                A force field object
        """
        self.ff = ff
        self.x0 = None
        self._init_initial()
        self._gx = np.zeros(self.ndof, float)

    def _init_initial(self):
        raise NotImplementedError

    ndof = property(lambda self: len(self.x0))

    def _update(self, x):
        raise NotImplementedError

    def reset(self):
        self._update(self.x0)

    def check_delta(self, x=None, eps=1e-4, zero=None):
        """Test the analytical derivatives"""
        if x is None:
            x = self.x0
        dxs = np.random.uniform(-eps, eps, (100, len(x)))
        if zero is not None:
            dxs[:,zero] = 0.0
        check_delta(self.fun, x, dxs)


class CartesianDOF(DOF):
    """Cartesian degrees of freedom for the optimizers"""
    def __init__(self, ff, gpos_rms=1e-5, dpos_rms=1e-3, select=None):
        """
           **Arguments:**

           ff
                A force field object.

           **Optional arguments:**

           gpos_rms, dpos_rms
                Thresholds that define the convergence. If all of the actual
                values drop below these thresholds, the minimizer stops.

                For each rms threshold, a corresponding max threshold is
                included automatically. The maximum of the absolute value of a
                component should be smaller than 3/sqrt(N) times the rms
                threshold, where N is the number of degrees of freedom.

           select
                A selection of atoms for which the hessian must be computed. If not
                given, the entire hessian is computed.

           **Convergence conditions:**

           gpos_rms
                The root-mean-square of the norm of the gradients of the atoms.

           dpos_rms
                The root-mean-square of the norm of the displacements of the
                atoms.
        """
        self.th_gpos_rms = gpos_rms
        self.th_dpos_rms = dpos_rms
        self.select = select
        DOF.__init__(self, ff)
        self._last_pos = None

    def _init_initial(self):
        """Return the initial value of the unknowns"""
        if self.select is None:
            self.x0 = self.ff.system.pos.ravel().copy()
        else:
            self.x0 = self.ff.system.pos[self.select].ravel().copy()
        self._pos = self.ff.system.pos.copy()
        self._dpos = np.zeros(self.ff.system.pos.shape, float)
        self._gpos = np.zeros(self.ff.system.pos.shape, float)

    def _update(self, x):
        if self.select is None:
            self._pos[:] = x.reshape(-1,3)
        else:
            self._pos[self.select] = x.reshape(-1,3)
        self.ff.update_pos(self._pos[:])

    def fun(self, x, do_gradient=False):
        """Computes the energy and optionally the gradient.

           **Arguments:**

           x
                The degrees of freedom

           **Optional arguments:**

           do_gradient
                When True, the gradient is also returned.
        """
        self._update(x)
        if do_gradient:
            self._gpos[:] = 0.0
            v = self.ff.compute(self._gpos)
            if self.select is None:
                self._gx[:] = self._gpos.ravel()
            else:
                self._gx[:] = self._gpos[self.select].ravel()
            return v, self._gx.copy()
        else:
            return self.ff.compute()

    def check_convergence(self):
        # When called for the first time, initialize _last_pos
        if self._last_pos is None:
            self._last_pos = self._pos.copy()
            self.converged = False
            self.conv_val = 2
            self.conv_worst = 'first_step'
            self.conv_count = -1
            return
        # Compute the values that have to be compared to the thresholds
        if self.select is None:
            gpossq = (self._gpos**2).sum(axis=1)
        else:
            gpossq = (self._gpos[self.select]**2).sum(axis=1)
        self.gpos_max = np.sqrt(gpossq.max())
        self.gpos_rms = np.sqrt(gpossq.mean())
        #
        self._dpos[:] = self._pos
        self._dpos -= self._last_pos
        if self.select is None:
            dpossq = (self._dpos**2).sum(axis=1)
        else:
            dpossq = (self._dpos[self.select]**2).sum(axis=1)
        self.dpos_max = np.sqrt(dpossq.max())
        self.dpos_rms = np.sqrt(dpossq.mean())
        # Compute a general value that has to go below 1.0 to have convergence.
        conv_vals = []
        if self.th_gpos_rms is not None:
            conv_vals.append((self.gpos_rms/self.th_gpos_rms, 'gpos_rms'))
            conv_vals.append((self.gpos_max/(self.th_gpos_rms*3), 'gpos_max'))
        if self.th_dpos_rms is not None:
            conv_vals.append((self.dpos_rms/self.th_dpos_rms, 'dpos_rms'))
            conv_vals.append((self.dpos_max/(self.th_dpos_rms*3), 'dpos_max'))
        if len(conv_vals) == 0:
            raise RuntimeError('At least one convergence criterion must be present.')
        self.conv_val, self.conv_worst = max(conv_vals)
        self.conv_count = sum(int(v>=1) for v, n in conv_vals)
        self.converged = (self.conv_count == 0)
        self._last_pos[:] = self._pos[:]


class BaseCellDOF(DOF):
    """Fractional coordinates and cell parameters"""
    def __init__(self, ff, gpos_rms=1e-5, dpos_rms=1e-3, gcell_rms=1e-5, dcell_rms=1e-3, do_frozen=False):
        """
           **Arguments:**

           ff
                A force field object.

           **Optional arguments:**

           gpos_rms, dpos_rms, gcell_rms, dcell_rms
                Thresholds that define the convergence. If all of the actual
                values drop below these thresholds, the minimizer stops.

                For each rms threshold, a corresponding max threshold is
                included automatically. The maximum of the absolute value of a
                component should be smaller than 3/sqrt(N) times the rms
                threshold, where N is the number of degrees of freedom.

           do_frozen
                When True, the fractional coordinates of the atoms are kept
                fixed.

           **Convergence conditions:**

           gpos_rms
                The root-mean-square of the norm of the gradients of the atoms.

           dpos_rms
                The root-mean-square of the norm of the displacements of the
                atoms.

           gcell_rms
                The root-mean-square of the norm of the gradients of the cell
                vectors.

           dcell_rms
                The root-mean-square of the norm of the displacements of the
                cell vectors.
        """
        self.th_gpos_rms = gpos_rms
        self.th_dpos_rms = dpos_rms
        self.th_gcell_rms = gcell_rms
        self.th_dcell_rms = dcell_rms
        self.do_frozen = do_frozen
        DOF.__init__(self, ff)
        self._last_pos = None
        self._last_cell = None

    def _init_initial(self):
        """Return the initial value of the unknowns"""
        cellvars = self.get_initial_cellvars()
        frac = np.dot(self.ff.system.pos, self.ff.system.cell.gvecs.T)
        if self.do_frozen:
            self.x0 = cellvars
            self.frac0 = frac
        else:
            self.x0 = np.concatenate([cellvars, frac.ravel()])
        self._pos = self.ff.system.pos.copy()
        self._dpos = np.zeros(self.ff.system.pos.shape, float)
        self._gpos = np.zeros(self.ff.system.pos.shape, float)
        self._cell = self.ff.system.cell.rvecs.copy()
        self._dcell = np.zeros(self._cell.shape, float)
        self._vtens = np.zeros(self._cell.shape, float)
        self._gcell = np.zeros(self._cell.shape, float)

    def _update(self, x):
        self._cell, index = self.x_to_rvecs(x)
        if self.do_frozen:
            frac = self.frac0
        else:
            frac = x[index:].reshape(-1,3)
        self._pos[:] = np.dot(frac, self._cell)
        self.ff.update_pos(self._pos[:])
        self.ff.update_rvecs(self._cell[:])
        return index

    def fun(self, x, do_gradient=False):
        """Computes the energy and optionally the gradient.

           **Arguments:**

           x
                The degrees of freedom

           **Optional arguments:**

           do_gradient
                When True, the gradient is also returned.
        """
        index = self._update(x)
        if do_gradient:
            self._gpos[:] = 0.0
            self._vtens[:] = 0.0
            v = self.ff.compute(self._gpos, self._vtens)
            self._gcell[:] = np.dot(self.ff.system.cell.gvecs, self._vtens)
            self._gx[:index] = self.grvecs_to_gx(self._gcell)
            if not self.do_frozen:
                self._gx[index:] = np.dot(self._gpos, self._cell.T).ravel()
            return v, self._gx.copy()
        else:
            return self.ff.compute()

    def check_convergence(self):
        # When called for the first time, initialize _last_pos and _last_cell
        if self._last_pos is None:
            self._last_pos = self._pos.copy()
            self._last_cell = self._cell.copy()
            self.converged = False
            self.conv_val = 2
            self.conv_worst = 'first_step'
            self.conv_count = -1
            return
        # Compute the values that have to be compared to the thresholds
        if not self.do_frozen:
            gpossq = (self._gpos**2).sum(axis=1)
            self.gpos_max = np.sqrt(gpossq.max())
            self.gpos_rms = np.sqrt(gpossq.mean())
            self._dpos[:] = self._pos
            self._dpos -= self._last_pos
        #
        dpossq = (self._dpos**2).sum(axis=1)
        self.dpos_max = np.sqrt(dpossq.max())
        self.dpos_rms = np.sqrt(dpossq.mean())
        #
        gcellsq = (self._gcell**2).sum(axis=1)
        self.gcell_max = np.sqrt(gcellsq.max())
        self.gcell_rms = np.sqrt(gcellsq.mean())
        self._dcell[:] = self._cell
        self._dcell -= self._last_cell
        #
        dcellsq = (self._dcell**2).sum(axis=1)
        self.dcell_max = np.sqrt(dcellsq.max())
        self.dcell_rms = np.sqrt(dcellsq.mean())
        # Compute a general value that has to go below 1.0 to have convergence.
        conv_vals = []
        if not self.do_frozen and self.th_gpos_rms is not None:
            conv_vals.append((self.gpos_rms/self.th_gpos_rms, 'gpos_rms'))
            conv_vals.append((self.gpos_max/(self.th_gpos_rms*3), 'gpos_max'))
        if self.th_dpos_rms is not None:
            conv_vals.append((self.dpos_rms/self.th_dpos_rms, 'dpos_rms'))
            conv_vals.append((self.dpos_max/(self.th_dpos_rms*3), 'dpos_max'))
        if self.th_gcell_rms is not None:
            conv_vals.append((self.gcell_rms/self.th_gcell_rms, 'gcell_rms'))
            conv_vals.append((self.gcell_max/(self.th_gcell_rms*3), 'gcell_max'))
        if self.th_dcell_rms is not None:
            conv_vals.append((self.dcell_rms/self.th_dcell_rms, 'dcell_rms'))
            conv_vals.append((self.dcell_max/(self.th_dcell_rms*3), 'dcell_max'))
        if len(conv_vals) == 0:
            raise RuntimeError('At least one convergence criterion must be present.')
        self.conv_val, self.conv_worst = max(conv_vals)
        self.conv_count = sum(int(v>=1) for v, n in conv_vals)
        self.converged = (self.conv_count == 0)
        self._last_pos[:] = self._pos[:]
        self._last_cell[:] = self._cell[:]

    def get_initial_cellvars(self):
        raise NotImplementedError

    def x_to_rvecs(self, x):
        raise NotImplementedError

    def grvecs_to_gx(self, grvecs):
        raise NotImplementedError


class FullCellDOF(BaseCellDOF):
    def get_initial_cellvars(self):
        cell = self.ff.system.cell
        if cell.nvec == 0:
            raise ValueError('A cell optimization requires a system that is periodic.')
        self.rvecs0 = cell.rvecs.copy()
        if cell.nvec == 3:
            return np.array([1.0, 1.0, 1.0, 0.0, 0.0, 0.0])
        elif cell.nvec == 2:
            return np.array([1.0, 1.0, 0.0])
        elif cell.nvec == 1:
            return np.array([1.0])
        else:
            raise NotImplementedError

    def x_to_rvecs(self, x):
        nvec = self.ff.system.cell.nvec
        index = (nvec*(nvec+1))/2
        scales = x[:index]
        if nvec == 3:
            deform = np.array([
                [    scales[0], 0.5*scales[5], 0.5*scales[4]],
                [0.5*scales[5],     scales[1], 0.5*scales[3]],
                [0.5*scales[4], 0.5*scales[3],     scales[2]],
            ])
        elif nvec == 2:
            deform = np.array([
                [    scales[0], 0.5*scales[2]],
                [0.5*scales[2],     scales[1]],
            ])
        elif nvec == 1:
            deform = np.array([[scales[0]]])
        else:
            raise NotImplementedError
        return np.dot(self.rvecs0, deform), index

    def grvecs_to_gx(self, grvecs):
        nvec = self.ff.system.cell.nvec
        gmat = np.dot(self.rvecs0.T, grvecs)
        if nvec == 3:
            gscales = np.array([
                gmat[0, 0], gmat[1, 1], gmat[2, 2],
                0.5*(gmat[1,2] + gmat[2,1]),
                0.5*(gmat[2,0] + gmat[0,2]),
                0.5*(gmat[0,1] + gmat[1,0]),
            ])
        elif nvec == 2:
            gscales = np.array([
                gmat[0, 0], gmat[1, 1],
                0.5*(gmat[0,1] + gmat[1,0]),
            ])
        elif nvec == 1:
            gscales = np.array([gmat[0, 0]])
        else:
            raise NotImplementedError
        return gscales


class AnisoCellDOF(BaseCellDOF):
    def get_initial_cellvars(self):
        cell = self.ff.system.cell
        if cell.nvec == 0:
            raise ValueError('A cell optimization requires a system that is periodic.')
        self.rvecs0 = cell.rvecs.copy()
        return np.ones(cell.nvec, float)

    def x_to_rvecs(self, x):
        index = self.ff.system.cell.nvec
        return self.rvecs0*x[:index].reshape(-1,1), index

    def grvecs_to_gx(self, grvecs):
        return (grvecs*self.rvecs0).sum(axis=1)


class IsoCellDOF(BaseCellDOF):
    def get_initial_cellvars(self):
        cell = self.ff.system.cell
        if cell.nvec == 0:
            raise ValueError('A cell optimization requires a system that is periodic.')
        self.rvecs0 = cell.rvecs.copy()
        return np.ones(1, float)

    def x_to_rvecs(self, x):
        return self.rvecs0*x[0], 1

    def grvecs_to_gx(self, grvecs):
        return (grvecs*self.rvecs0).sum()
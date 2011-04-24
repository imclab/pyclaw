#!/usr/bin/env python
# encoding: utf-8
r"""
Module containg the PetClaw solvers

This module contains the pure and wrapped PetClaw solvers.  All 
PetClaw solvers inherit from the :class:`ClawSolver` superclass which in turn 
inherits from the :class:`~petclaw.evolve.solver.Solver` superclass.  As such, 
the only solver classes that should be directly used should be the 
dimensionally dependent ones such as :class:`PetClawSolver1D`.

:Authors:
    Amal Alghamdi
    David Ketcheson
"""
# ============================================================================
#      Copyright (C) 2010 David I. Ketcheson <david.ketcheson@kaust.edu.sa>
#
#  Distributed under the terms of the Berkeley Software Distribution (BSD) 
#  license
#                     http://www.opensource.org/licenses/
# ============================================================================

import numpy as np

import pdb # debugger


from pyclaw.evolve.clawpack import ClawSolver, ClawSolver1D, ClawSolver2D, start_step, src
from pyclaw.evolve import limiters

from petsc4py import PETSc

#This should be modified so we don't depend on mpi4py:
try:
  from mpi4py import MPI
except:
  raise Exception("Unable to communicate cfl")

# ============================================================================
#  Generic PetClaw solver class
# ============================================================================
class PetClawSolver(ClawSolver):
    r"""
    Generic PetClaw solver
    
    All PetClaw solvers inherit from this base class.

    See superclass ClawSolver for documentation of attributes.
    
    :Initialization:
    
    Input:
     - *data* - (:class:`~petclaw.data.Data`) Data object, the solver will look 
       for the named variables to instantiate itself.    
    Output:
     - (:class:`PetClawSolver`) - Initialized petclaw solver
    """
    
    # ========== Boundary Conditions ==================================
    def qbc(self,grid,t,q):
        """
        Returns an array with the ghost cells filled.
        """
        
        qbc = grid.ghosted_q
        for i,dim in enumerate(grid.dimensions):
            #If a user defined boundary condition is being used, send it on,
            #otherwise roll the axis to front position and operate on it
            if dim.mthbc_lower == 0:
                self.qbc_lower(grid,dim,qbc)
            else:
                self.qbc_lower(grid,dim,np.rollaxis(qbc,i+1,1))
            if dim.mthbc_upper == 0:
                self.qbc_upper(grid,dim,qbc)
            else:
                self.qbc_upper(grid,dim,np.rollaxis(qbc,i+1,1))
        return qbc

    def qbc_lower(self,grid,dim,qbc):
        r"""
        This function should be upstreamed to the pyclaw.evolve.solver.Solver class
        """
        # User defined functions
        if dim.mthbc_lower == 0: self.user_bc_lower(grid,dim,qbc)
        # Zero-order extrapolation
        elif dim.mthbc_lower == 1:
            if dim.nstart == 0:
                for i in xrange(grid.mbc):
                    qbc[:,i,...] = qbc[:,grid.mbc,...]
        # Periodic
        elif dim.mthbc_lower == 2:
            pass # Amal: this is implemented automatically by petsc4py
            
        # Solid wall bc
        # Matteo: I've used three if statements to impose correctly this BC for both 1D and 2D
        # simulations. Is this the most efficient way?
        elif dim.mthbc_lower == 3:
             if dim.nstart == 0:
                if grid.ndim == 1:
                    for i in xrange(grid.mbc):
                        qbc[:,i,...] = qbc[:,grid.mbc+1-i,...]
                        qbc[1,i,...] = -qbc[1,grid.mbc+1-i,...] # Negate normal velocity
                elif grid.ndim == 2:
                     if dim.name == 'x':  # left boundary in the x direction
                         for i in xrange(grid.mbc):
                             qbc[:,i,...] = qbc[:,grid.mbc+1-i,...]
                             qbc[1,i,...] = -qbc[1,grid.mbc+1-i,...] # Negate normal velocity
                     else: # lower boundary in the y direction
                         for i in xrange(grid.mbc):
                             qbc[:,i,...] = qbc[:,grid.mbc+1-i,...]
                             qbc[2,i,...] = -qbc[2,grid.mbc+1-i,...]  # Negate normal velocity
              
                else:
                    raise NotImplementedError("3D wall boundary condition %s not implemented" % x.mthbc_lower)
        else:
            raise NotImplementedError("Boundary condition %s not implemented" % x.mthbc_lower)


    def qbc_upper(self,grid,dim,qbc):
        r"""
        This function should be upstreamed to the pyclaw.evolve.solver.Solver class
        """
        # User defined functions
        if dim.mthbc_upper == 0: self.user_bc_upper(grid,dim,qbc)
        # Zero-order extrapolation
        elif dim.mthbc_upper == 1:
            if dim.nend == dim.n :
                for i in xrange(grid.mbc):
                    qbc[:,-i-1,...] = qbc[:,-grid.mbc-1,...] 
 	    
        elif dim.mthbc_upper == 2:
            # Periodic
            pass # Amal: this is implemented automatically by petsc4py

        # Solid wall bc
        # Matteo: I've used three if statements to impose correctly this BC for both 1D and 2D
        # simulations. Is this the most efficient way?
        elif dim.mthbc_upper == 3:
            if dim.nend == dim.n:
                if grid.ndim == 1:
                    for i in xrange(grid.mbc):
                        qbc[:,-i-1,...] = qbc[:,-grid.mbc-2+i,...]
                        qbc[1,-i-1,...] = -qbc[1,-grid.mbc-2+i,...] # Negate normal velocity
                elif grid.ndim == 2:
                     if dim.name == 'x': # right boundary in the x direction
                         for i in xrange(grid.mbc):
                             qbc[:,-i-1,...] = qbc[:,-grid.mbc-2+i,...]
                             qbc[1,-i-1,...] = -qbc[1,-grid.mbc-2+i,...] # Negate normal velocity
                     else: # upper boundary in the y direction
                         for i in xrange(grid.mbc):
                             qbc[:,-i-1,...] = qbc[:,-grid.mbc-2+i,...]
                             qbc[2,-i-1,...] = -qbc[2,-grid.mbc-2+i,...] # Negate normal velocity
              
                else:
                    raise NotImplementedError("3D wall boundary condition %s not implemented" % x.mthbc_lower)
        else:
            raise NotImplementedError("Boundary condition %s not implemented" % x.mthbc_lower)

    def communicateCFL(self):
        if self.dt_variable:
          comm = MPI.COMM_WORLD #Amal:should be consistent with petsc commworld
          max_cfl = np.array([0.])
          cfl1 = np.array([self.cfl])
          comm.Allreduce(cfl1, max_cfl, MPI.MAX)
          self.cfl = max_cfl[0]
 

# ============================================================================
#  ClawPack 1d Solver Class
# ============================================================================
class PetClawSolver1D(PetClawSolver,ClawSolver1D):
    r"""
    PetClaw solver for 1D problems using classic Clawpack algorithms.

    This class implements nothing; it just inherits from PetClawSolver and
    ClawSolver1D.
    """

# ============================================================================
#  PetClaw 2d Solver Class
# ============================================================================
class PetClawSolver2D(PetClawSolver,ClawSolver2D):
    r"""
    PetClaw solver for 2D problems using classic Clawpack algorithms.

    This class implements nothing; it just inherits from PetClawSolver and
    ClawSolver2D.
    
    Note that only the fortran routines are supported for now in 2D.
    """

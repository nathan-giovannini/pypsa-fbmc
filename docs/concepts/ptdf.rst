Power Transfer Distribution Factors (PTDF)
==========================================

The PTDF matrix encodes how power injections at individual buses propagate to flows on
network branches. It is the core linear sensitivity tool behind FBMC.

Nodal PTDF
----------

For a DC power flow approximation the flow on branch :math:`b` is a linear function of
bus injections:

.. math::

   f_b = \sum_{n=1}^{N} PTDF_{b,n} \cdot p_n

where :math:`p_n` is the net injection at bus :math:`n` (generation minus load) and the
slack bus absorbs any imbalance. The entry :math:`PTDF_{b,n}` is therefore the fraction
of a 1 MW injection at bus :math:`n` (and withdrawal at the slack) that flows on
branch :math:`b`.

The full matrix :math:`\mathbf{H} \in \mathbb{R}^{B \times N}` is computed from the
branch susceptances and the network topology:

.. math::

   \mathbf{H} = \mathbf{B}_f \, \mathbf{B}_{bus}^{+}

where :math:`\mathbf{B}_f` is the branch susceptance matrix and
:math:`\mathbf{B}_{bus}^{+}` is the Moore–Penrose pseudo-inverse of the nodal
susceptance (Laplacian) matrix, with the slack column/row removed.

.. note::

   PyPSA computes the PTDF internally via ``SubNetwork.calculate_PTDF()``.
   pypsa-fbmc wraps the result as an ``xarray.DataArray`` with named dimensions
   ``(branch, Bus)``.

Zonal PTDF
----------

The market is operated at zone level, not bus level. The *zonal PTDF* (zPTDF) gives the
sensitivity of branch flow to a change in a zone's *net position* :math:`NP_z`:

.. math::

   zPTDF_{b,z}
   = \sum_{n \in \mathcal{N}} GSK_{z,n} \cdot PTDF_{b,n}
   = \bigl(\mathbf{H} \cdot \mathbf{GSK}^{\top}\bigr)_{b,z}

where :math:`GSK_{z,n}` is the Generation Shift Key (see :doc:`gsk`) describing how
bus :math:`n` responds to a unit change in zone :math:`z`'s net position.

The resulting matrix has dimensions :math:`(B_{CNEC} \times Z)` — one row per monitored
CNEC and one column per bidding zone.

Security-constrained PTDF (N-1)
---------------------------------

When security constraints are enabled, the PTDF is extended to cover
post-contingency flows using the Branch Outage Distribution Factor (BODF).

The BODF entry :math:`BODF_{i,j}` gives the additional fraction of branch :math:`j`'s
pre-contingency flow that is redirected onto branch :math:`i` when branch :math:`j`
trips:

.. math::

   f_i^{N\text{-}1}(j) = f_i^{N\text{-}0} + BODF_{ij} \cdot f_j^{N\text{-}0}

Combining with the nodal PTDF yields the security-constrained sensitivities used to
form the N-1 CNEC rows in the zPTDF matrix.

Implementation
--------------

* ``src/fbmc/core/parameters/ptdf.py`` – nodal and zonal PTDF calculation.
* ``src/fbmc/core/parameters/security_constrained.py`` – BODF computation and
  application.

The main entry point is :func:`fbmc.core.parameters.ptdf.calculate_zonal_ptdf`.

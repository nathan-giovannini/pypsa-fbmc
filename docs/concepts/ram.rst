Remaining Available Margin (RAM)
=================================

The Remaining Available Margin (RAM) is the capacity headroom available on a Critical
Network Element (CNEC) for cross-zonal power exchanges. RAM is the right-hand side of
the FBMC capacity constraints.

Reference flow
--------------

The *reference flow* on CNEC :math:`b` is the expected flow under the market's net
positions, computed from the base-case flow :math:`f_b^{bc}` and the base-case net
positions :math:`NP_z^{bc}`:

.. math::

   f_b^{ref}
   = f_b^{bc}
   - \sum_{z \in \mathcal{Z}} zPTDF_{b,z} \cdot NP_z^{bc}


The capacity constraint is expressed via the *Remaining Available Margin* (RAM):

.. math::

   \underline{RAM}_{\ell,t} \;\le\; \sum_n z\text{PTDF}_{\ell,n}\, p_{n,t} \;\le\; \overline{RAM}_{\ell,t}
   \qquad \forall \ell \in \mathcal{C},\; \forall t \in \mathcal{T}

where the upper and lower RAM values are defined as:

.. math::

   \overline{RAM}_{\ell,t}  &= \overline{F}_\ell - F^{\mathrm{REF}}_{\ell,t} - S_{\ell}
     \qquad \forall \ell \in \mathcal{C},\; \forall t \in \mathcal{T} \\
   \underline{RAM}_{\ell,t} &= -\overline{F}_\ell - F^{\mathrm{REF}}_{\ell,t} + S_{\ell}
     \qquad \forall \ell \in \mathcal{C},\; \forall t \in \mathcal{T}

Here :math:`\overline{F}_\ell` is the thermal limit, :math:`F^{\mathrm{REF}}_{\ell,t}` is
the reference flow (computed from the reference programme), and :math:`S_{\ell}` is the
flow reliability margin (FRM) / safety slack applied to the line.

N-1 CNECs (security constraints)
----------------------------------

When :attr:`~fbmc.settings.FBMCConfig.add_security_constraints` is ``True``, the CNEC
set is extended with N-1 pairs :math:`(\ell, o)` where :math:`\ell` is a monitored branch
and :math:`o` is an outaged branch. The post-contingency flow is:

.. math::

   f_\ell^{N\text{-}1}(o)
   = f_\ell^{N\text{-}0} + BODF_{\ell,o} \cdot f_o^{N\text{-}0}

The RAM bounds for N-1 CNECs follow the same structure as N-0, but indexed over
outage scenarios as well:

.. math::

   \overline{RAM}_{\ell,o,t}  &= \overline{F}_\ell - F^{\mathrm{REF}}_{\ell,o,t} - S_{\ell,o}
     \qquad \forall (\ell,o) \in \mathcal{C},\; \forall t \in \mathcal{T} \\
   \underline{RAM}_{\ell,o,t} &= -\overline{F}_\ell - F^{\mathrm{REF}}_{\ell,o,t} + S_{\ell,o}
     \qquad \forall (\ell,o) \in \mathcal{C},\; \forall t \in \mathcal{T}

Here :math:`F^{\mathrm{REF}}_{\ell,o,t}` is the reference flow on branch :math:`\ell`
after outage :math:`o`, and :math:`S_{\ell,o}` is the FRM slack for that CNEC pair.


The subtraction of the zPTDF term removes the contribution of the base-case net
positions so that the RAM represents headroom from a *zero net-position* reference point.

Flow Reliability Margin (FRM)
------------------------------

A safety buffer is reserved on every branch to account for uncertainties not captured
by the model (e.g. forecast errors, unmodelled loop flows). The Flow Reliability Margin
is a fixed fraction :math:`\alpha` of the thermal capacity :math:`c_b`:

.. math::

   FRM_b = \alpha \cdot c_b

The parameter :math:`\alpha` is :attr:`~fbmc.settings.FBMCConfig.reliability_margin_factor`
(default ``0.0``).

RAM formulas
------------

After reserving the FRM and accounting for the reference flow, the available margins are:

.. math::

   RAM_b^{upper}
   = c_b - FRM_b - f_b^{ref}
   = (1 - \alpha)\,c_b - f_b^{ref}

.. math::

   RAM_b^{lower}
   = -c_b - FRM_b - f_b^{ref}
   = -(1 - \alpha)\,c_b - f_b^{ref}

These bounds define the FBMC constraint for each CNEC:

.. math::

   RAM_b^{lower}
   \;\le\;
   \sum_{z} zPTDF_{b,z} \cdot NP_z
   \;\le\;
   RAM_b^{upper}

Minimum RAM
-----------

To prevent situations where the base-case flow already consumes the entire capacity,
a minimum RAM floor can be enforced:

.. math::

   RAM_b^{upper} \;\ge\; \beta \cdot c_b, \qquad
   RAM_b^{lower} \;\le\; -\beta \cdot c_b

where :math:`\beta` is :attr:`~fbmc.settings.FBMCConfig.min_ram` (default ``0.0``).
Setting :math:`\beta > 0` guarantees that at least a fraction :math:`\beta` of the
thermal capacity remains available for cross-zonal trade even when the branch is
heavily loaded in the base case.

Upper-RAM-only mode
-------------------

When :attr:`~fbmc.settings.FBMCConfig.upper_ram_only_flag` is ``True``, only the upper
RAM constraint is enforced. This is relevant in asymmetric market designs (e.g. the
Advanced Hybrid Coupling scheme used for Ukraine interconnection) where reverse flows
are treated differently.

Implementation
--------------

* ``src/fbmc/core/parameters/ram.py``
* Key functions:

  - :func:`fbmc.core.parameters.ram.calculate_ram` – compute upper and lower RAM arrays.
  - :func:`fbmc.core.parameters.ram.calculate_flow_reliability_margin` – compute FRM.
  - :func:`fbmc.core.parameters.ram.calculate_branch_capacity` – extract thermal limits.

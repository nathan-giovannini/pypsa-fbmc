Base Case Strategies
====================

The *base case* is the initial operating point of the nodal network used to compute
reference flows for the RAM calculation (see :doc:`../concepts/ram`). It represents
the expected dispatch state before any cross-zonal trades are applied.

The strategy is controlled by :attr:`~fbmc.settings.FBMCConfig.base_case_strategy`.

Strategies
----------

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Strategy
     - Description
   * - ``ZERO_FLOWS``
     - All branch flows and bus injections are set to zero. This is the most
       conservative choice: the reference flow :math:`f_b^{bc} = 0` on every
       branch, so RAM is not reduced by any pre-existing flow.
   * - ``NODAL_OPTIMUM``
     - A nodal optimal power flow (OPF) is solved on the nodal network. The
       resulting dispatch sets the base-case flows. This reflects the
       physically optimal operating point and is the recommended default for
       realistic studies.
   * - ``SECURITY_CONSTRAINED_NODAL_OPTIMUM``
     - As ``NODAL_OPTIMUM``, but the nodal OPF is solved under N-1 security
       constraints. Branch outages are limited to non-bridge branches. This
       produces a base case that is robust to single contingencies.
   * - ``CUSTOM``
     - The nodal network is used as provided, without any modification or
       re-dispatch. Useful when an external tool has already set the operating
       point.

Effect on RAM
-------------

The base-case flow :math:`f_b^{bc}` enters directly into the reference flow
calculation:

.. math::

   f_b^{ref} = f_b^{bc} - \sum_{z} zPTDF_{b,z} \cdot NP_z^{bc}

A larger base-case flow reduces the available RAM, tightening the FBMC
constraints. Choosing ``ZERO_FLOWS`` therefore yields the most permissive
constraints, while ``NODAL_OPTIMUM`` gives physically realistic constraints.

Implementation
--------------

* ``src/fbmc/core/inputs/base_case.py``
* Entry point: :func:`fbmc.core.inputs.base_case.prepare_base_case`.

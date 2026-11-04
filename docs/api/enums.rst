Enumerations
============

.. autoclass:: fbmc.enums.GSKStrategy
   :members:
   :undoc-members:

.. autoclass:: fbmc.enums.BaseCaseStrategy
   :members:
   :undoc-members:

.. autoclass:: fbmc.enums.CNECStrategy
   :members:
   :undoc-members:

GSKStrategy values
------------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Value
     - Description
   * - ``CURRENT_GENERATION``
     - Weights buses proportionally to their current dispatch level.
   * - ``ADJUSTABLE_CAP``
     - Weights buses by installed *dispatchable* generation capacity (carriers
       configured via ``gsk_kwargs``).
   * - ``P_NOM``
     - Weights buses by total installed capacity across all carriers.
   * - ``BUS_P``
     - Uses current nodal net power (snapshot-dependent).
   * - ``MERIT_ORDER``
     - Merit-order based, with Gaussian perturbation.
   * - ``ITERATIVE_UNCERTAINTY``
     - Monte-Carlo over renewable uncertainty scenarios.
   * - ``ITERATIVE_FBMC``
     - ITERATIVE_UNCERTAINTY plus an outer FBMC convergence loop.

BaseCaseStrategy values
-----------------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Value
     - Description
   * - ``ZERO_FLOWS``
     - All line flows and bus power values set to zero. Equivalent to assuming
       the reference point has no pre-existing cross-zonal flows.
   * - ``NODAL_OPTIMUM``
     - Run a nodal optimal power flow; use the resulting dispatch as the base case.
   * - ``SECURITY_CONSTRAINED_NODAL_OPTIMUM``
     - As ``NODAL_OPTIMUM`` but with N-1 security constraints active during the
       nodal solve.
   * - ``CUSTOM``
     - Use the network as provided without modification.

CNECStrategy values
-------------------

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Value
     - Description
   * - ``ALL``
     - Monitor all non-bridge branches in the network (N-0, plus N-1 when
       security constraints are enabled).
   * - ``CUSTOM``
     - Monitor only the branches passed explicitly to ``zonal_net.fbmc.run(...)`` or
       ``zonal_net.fbmc.create_model(...)``.

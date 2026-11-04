results — extract results after solving
========================================

.. automethod:: fbmc.accessor.FBMCAccessor.results

Usage
-----

Call :meth:`~fbmc.accessor.FBMCAccessor.results` after the solver has found an optimal
solution:

.. code-block:: python

   import fbmc
   from fbmc import FBMCConfig

   config = FBMCConfig()

   result = zonal_net.fbmc.run(nodal_net, config)

   print(result.net_positions)       # DataFrame[snapshots × zones]
   print(result.dispatch_results)    # generator / storage dispatch

If the model did not solve to optimality a :class:`ValueError` is raised.

Return value
------------

Returns an :class:`~fbmc.types.FBMCResult` with the following attributes:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Attribute
     - Description
   * - ``net_positions``
     - ``DataFrame[snapshots × zones]`` — optimal zone net positions (MW).
   * - ``dispatch_results``
     - :class:`~fbmc.types.DispatchResult` with generator dispatch, storage dispatch,
       link flows, storage levels, and (if LP) water values.
   * - ``fbmc_parameters``
     - Per-subnet zonal PTDFs and RAM values, for inspection or post-processing.
   * - ``zonal_net``
     - The solved zonal :class:`pypsa.Network` with all time-series results attached.
   * - ``base_case``
     - The nodal network in its base-case state (used to derive PTDFs and RAM).

See also
--------

* :doc:`run` for the recommended one-step workflow.
* :doc:`solve` for staged solving.
* :class:`~fbmc.types.FBMCResult` for the full type definition.
* :class:`~fbmc.types.DispatchResult` for the dispatch result type.

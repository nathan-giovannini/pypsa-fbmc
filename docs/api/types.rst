Return types
============

FBMCResult
----------

.. autoclass:: fbmc.types.FBMCResult
   :members:

Accessing results
~~~~~~~~~~~~~~~~~

.. code-block:: python

   result = zonal_net.fbmc.run(nodal_net, config)

   # Zone net positions: DataFrame[snapshots × zones]  (MW)
   print(result.net_positions)

   # Generator dispatch: DataFrame[snapshots × generators]  (MW)
   print(result.dispatch_results.generators_p)

   # zonal PTDF for the first sub-network
   subnet_key = list(result.fbmc_parameters.keys())[0]
   print(result.fbmc_parameters[subnet_key].z_ptdf)

   # Upper RAM values
   print(result.fbmc_parameters[subnet_key].upper_ram)

DispatchResult
--------------

.. autoclass:: fbmc.types.DispatchResult
   :members:

SubnetFBMCParameters
---------------------

.. autoclass:: fbmc.types.SubnetFBMCParameters
   :members:

The ``z_ptdf`` field is an ``xarray.DataArray`` with dimensions
``(cnec, Zone[, snapshot])``. Each CNEC row is the zonal sensitivity of that branch's
flow to a 1 MW change in each zone's net position.

``upper_ram`` and ``lower_ram`` share the same ``cnec`` coordinate and represent the
capacity bounds for the FBMC constraints (see :doc:`/concepts/ram`).

Input parameter types
---------------------

These types are used internally but can be useful for advanced usage (e.g. computing
FBMC parameters without running the full optimisation).

.. autoclass:: fbmc.types.InputParameters
   :members:

.. autoclass:: fbmc.types.InputParametersSubnet
   :members:

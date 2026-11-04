Optional redispatch workflow
============================

Redispatch is available as an **optional workflow** after FBMC market clearing.

It is intentionally separate from :meth:`fbmc.accessor.FBMCAccessor.run`, so first-time
users can learn the core FBMC workflow without having to understand redispatch at the same
time.

When to use redispatch
----------------------

Use redispatch if you want to:

* take the FBMC dispatch as a reference schedule
* run a second nodal optimization
* optionally include security constraints in that second step

Basic usage
-----------

.. code-block:: python

   import fbmc

   result = zonal_net.fbmc.run(nodal_net, config)

   rd_net, rd_cost = fbmc.redispatch.run(
       nodal_net,
       result.dispatch_results,
   )

Inputs
------

``fbmc.redispatch.run(...)`` expects:

* a nodal :class:`pypsa.Network`
* a :class:`fbmc.types.DispatchResult` from a previous FBMC run

Optional arguments let you control:

* which carriers can redispatch
* whether redispatch should be security-constrained
* the load shedding penalty
* solver and model creation options

What it returns
---------------

The function returns:

* the solved nodal redispatch network
* the total redispatch cost

Design note
-----------

Redispatch is not part of the default FBMC path.
This repository treats it as an additional tool layered on top of FBMC rather than part of
the main `zonal_net.fbmc.run(...)` lifecycle.

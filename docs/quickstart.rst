Quick Start
===========

This page is written for first-time users.

If you are new to the repository, follow the steps in this order:

1. install the package and a solver
2. build a nodal PyPSA network
3. add ``zone_name`` labels to buses
4. convert the nodal network to a zonal network
5. call :meth:`fbmc.accessor.FBMCAccessor.run`
6. inspect the returned :class:`fbmc.types.FBMCResult`

Installation
------------

Requires Python 3.11 or later.

.. code-block:: bash

   git clone https://github.com/WouterKoksNL/pypsa-fbmc
   cd pypsa-fbmc
   pip install .

Solver setup
------------

The default configuration uses **Gurobi**.

If you want to use another solver supported by
`linopy <https://linopy.readthedocs.io>`_, change the solver name in
``config.solver_kwargs``.

For example:

.. code-block:: python

   import fbmc

   config = fbmc.FBMCConfig.from_base_yaml()
   config.solver_kwargs["solver_name"] = "highs"

Before you start
----------------

Your nodal :class:`pypsa.Network` should have:

* buses
* loads
* generators or other supply-side assets
* AC branches with valid reactances
* a ``zone_name`` column on ``nodal_net.buses``

Minimal first run
-----------------

.. code-block:: python

   import pypsa
   import fbmc

   nodal_net = pypsa.Network()
   nodal_net.set_snapshots(["1", "2"])
   nodal_net.add("Bus", ["A1", "B1", "B2"])
   nodal_net.buses.loc[:, "zone_name"] = ["A", "B", "B"]
   nodal_net.add("Line", "B1-A1", bus0="B1", bus1="A1", x=1, s_nom=12)
   nodal_net.add("Line", "B1-B2", bus0="B1", bus1="B2", x=1, s_nom=12)
   nodal_net.add("Line", "A1-B2", bus0="A1", bus1="B2", x=1, s_nom=12)
   nodal_net.add("Generator", "gen_A1", bus="A1", p_nom=100, marginal_cost=400)
   nodal_net.add("Generator", "gen_B1", bus="B1", p_nom=100, marginal_cost=100)
   nodal_net.add("Generator", "gen_B2", bus="B2", p_nom=100, marginal_cost=200)
   nodal_net.add("Load", "load_A1", bus="A1", p_set=[15, 15])

   zonal_net = nodal_net.fbmc.to_zonal(nodal_net.buses["zone_name"])

   config = fbmc.FBMCConfig.from_base_yaml()
   result = zonal_net.fbmc.run(nodal_net, config)

What the one-step workflow does
-------------------------------

:meth:`fbmc.accessor.FBMCAccessor.run` performs the full default FBMC workflow:

1. validate the nodal and zonal inputs
2. prepare the base-case nodal state
3. compute or validate the GSK
4. choose CNECs
5. build the zonal FBMC model
6. solve it
7. return the final :class:`fbmc.types.FBMCResult`

What you get back
-----------------

The returned :class:`fbmc.types.FBMCResult` contains:

* ``net_positions`` – zone net positions by snapshot
* ``dispatch_results`` – generator, storage, and link dispatch results
* ``fbmc_parameters`` – per-subnet zPTDF and RAM data
* ``zonal_net`` – the solved zonal network
* ``base_case`` – the nodal base-case network used to derive FBMC parameters

Example:

.. code-block:: python

   print(result.net_positions)
   print(result.dispatch_results.generators_p)

Step-by-step mode
-----------------

If you want to inspect the stages manually:

.. code-block:: python

   zonal_net.fbmc.create_model(nodal_net, config)
   zonal_net.fbmc.solve()
   result = zonal_net.fbmc.results()

Use this mode for debugging, teaching, or checking intermediate model state.

Custom GSK input
----------------

If you already know the GSK you want to use, pass it explicitly:

.. code-block:: python

   gsk = {
       snapshot: gsk_df
       for snapshot in nodal_net.snapshots
   }

   result = zonal_net.fbmc.run(nodal_net, config, gsk=gsk)

Optional redispatch
-------------------

Redispatch is an optional workflow layered on top of FBMC.
It is **not** part of the default ``run()`` path.

.. code-block:: python

   rd_net, rd_cost = fbmc.redispatch.run(
       nodal_net,
       result.dispatch_results,
   )

Where to go next
----------------

* :doc:`api/run`
* :doc:`api/to_zonal`
* :doc:`api/create_model`
* :doc:`api/solve`
* :doc:`api/results`
* :doc:`workflows/redispatch`

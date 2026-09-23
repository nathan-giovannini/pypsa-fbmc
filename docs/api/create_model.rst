create_model — build the FBMC model
=====================================

.. automethod:: fbmc.accessor.FBMCAccessor.create_model

Workflow
--------

Calling :meth:`~fbmc.accessor.FBMCAccessor.create_model` executes the following
pipeline internally:

1. **Input validation** – checks that the zonal and nodal networks are consistent.
2. **Topology detection** – runs ``determine_network_topology()`` on the nodal network
   if sub-networks have not yet been identified.
3. **Input parameters** –

   a. Prepares the base-case nodal network according to
      :attr:`~fbmc.settings.FBMCConfig.base_case_strategy`.
   b. Computes (or validates) the GSK matrix.
   c. Selects CNECs and optionally adds N-1 contingency rows.

4. **FBMC model setup** –

   a. Computes nodal and zonal PTDFs.
   b. Computes RAM (upper and lower) for every CNEC.
   c. Creates zone net-position variables and removes nodal balance constraints.
   d. Injects FBMC capacity constraints into the linopy model.

After calling ``create_model``, continue with
:meth:`fbmc.accessor.FBMCAccessor.solve` and
:meth:`fbmc.accessor.FBMCAccessor.results`.

.. code-block:: python

   import fbmc                       # registers pypsa.Network.fbmc
   from fbmc import FBMCConfig

   config = FBMCConfig()

   zonal_net.fbmc.create_model(nodal_net, config)
   zonal_net.fbmc.solve()
   result = zonal_net.fbmc.results()

Providing a custom GSK
----------------------

The ``gsk`` parameter accepts:

* a plain dict ``{zone: {bus: weight, ...}, ...}``
* a snapshot-keyed dict ``{snapshot: {zone: {bus: weight}}}`` for time-varying GSKs

.. code-block:: python

   zonal_net.fbmc.create_model(
       nodal_net,
       config,
       gsk={"Zone_A": {"Bus1": 0.7, "Bus2": 0.3}},
   )

Omitting ``gsk`` (or passing ``None``) triggers automatic calculation according to
:attr:`~fbmc.settings.FBMCConfig.gsk_strategy`.

See also
--------

* :doc:`/concepts/fbmc_overview` for the algorithm steps.
* :doc:`run` for the recommended one-step user workflow.
* :doc:`to_zonal` for converting a nodal network to a zonal one.
* :doc:`solve` for solving a previously created model.
* :doc:`results` for extracting results after solving.
* :class:`~fbmc.types.FBMCResult` for the result type.
* :class:`~fbmc.settings.FBMCConfig` for all configuration options.

solve — solve a previously created FBMC model
=============================================

.. automethod:: fbmc.accessor.FBMCAccessor.solve

When to use this
----------------

Use ``solve()`` when you already called
:meth:`fbmc.accessor.FBMCAccessor.create_model` and want to keep the stages explicit.

Example
-------

.. code-block:: python

   zonal_net.fbmc.create_model(nodal_net, config)
   zonal_net.fbmc.solve()
   result = zonal_net.fbmc.results()

Solver overrides
----------------

You can pass temporary solver overrides directly to ``solve()``:

.. code-block:: python

   zonal_net.fbmc.solve(solver_name="highs")

This is useful when you want to keep the base configuration unchanged but try a different
solver or solver option in one run.

Failure behavior
----------------

If no model has been created yet, ``solve()`` raises :class:`ValueError`.

If the optimization does not terminate with an optimal solution, ``solve()`` raises
:class:`ValueError` and no result object is kept as valid solved state.

See also
--------

* :doc:`run`
* :doc:`create_model`
* :doc:`results`

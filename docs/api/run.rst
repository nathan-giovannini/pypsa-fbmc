run — recommended one-step workflow
===================================

.. automethod:: fbmc.accessor.FBMCAccessor.run

When to use this
----------------

This is the recommended entry point for most users.

Use :meth:`fbmc.accessor.FBMCAccessor.run` when you want:

* the simplest FBMC workflow
* one call that validates, builds, solves, and extracts results
* an API that is easy to teach and easy to script

Example
-------

.. code-block:: python

   import fbmc

   zonal_net = nodal_net.fbmc.to_zonal(nodal_net.buses["zone_name"])
   config = fbmc.FBMCConfig.from_base_yaml()
   result = zonal_net.fbmc.run(nodal_net, config)

What happens internally
-----------------------

Calling ``run(...)`` performs the staged workflow in order:

1. :meth:`fbmc.accessor.FBMCAccessor.create_model`
2. :meth:`fbmc.accessor.FBMCAccessor.solve`
3. :meth:`fbmc.accessor.FBMCAccessor.results`

That means you can always switch to the explicit path later if you need to debug or inspect
intermediate steps.

Return value
------------

Returns an :class:`fbmc.types.FBMCResult`.

See also
--------

* :doc:`to_zonal`
* :doc:`create_model`
* :doc:`solve`
* :doc:`results`

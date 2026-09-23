to_zonal — convert a nodal network to a zonal network
=======================================================

.. automethod:: fbmc.accessor.FBMCAccessor.to_zonal

Usage
-----

Each bus in the nodal network must carry a ``zone_name`` label.  Pass the resulting
Series (or any mapping of bus → zone) to ``to_zonal``:

.. code-block:: python

   import pypsa
   import fbmc                       # registers pypsa.Network.fbmc

   nodal_net = pypsa.Network()
   nodal_net.add("Bus", ["A1", "B1", "B2"])
   nodal_net.buses["zone_name"] = ["A", "B", "B"]

   zonal_net = nodal_net.fbmc.to_zonal(nodal_net.buses.zone_name)

The returned network has one bus per unique zone, with generators, loads, and storage
units aggregated accordingly.  Cross-zone lines become links in the zonal network.

See also
--------

* :doc:`run` for the next step — running FBMC on the zonal network.
* :func:`fbmc.network.network_conversion.nodal_to_zonal` for the
  underlying conversion function.

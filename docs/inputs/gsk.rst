Generation Shift Keys (GSK)
===========================

The Generation Shift Key (GSK) matrix translates a zonal net-position change into bus-level
power injections. It is required to bridge the gap between the zonal market model and the
nodal physical network.

Definition
----------

For zone :math:`z`, the GSK entry at bus :math:`n` is the share of a unit increase in
zone :math:`z`'s net position that is injected at bus :math:`n`:

.. math::

   GSK_{z,n} \geq 0,
   \qquad
   \sum_{n \in \mathcal{N}_z} GSK_{z,n} = 1
   \quad \forall\, z \in \mathcal{Z}

where :math:`\mathcal{N}_z` is the set of buses belonging to zone :math:`z`. Buses
outside zone :math:`z` have :math:`GSK_{z,n} = 0`.

The GSK matrix has dimensions :math:`(Z \times N)` where :math:`Z` is the number of
zones and :math:`N` the number of buses in the network.

GSK strategies
--------------

pypsa-fbmc supports several methods for computing the GSK, controlled by
:attr:`~fbmc.settings.FBMCConfig.gsk_strategy`.

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Strategy
     - Description
   * - ``CURRENT_GENERATION``
     - Weights buses by their current dispatch level
       :math:`p_n^{gen}`:

       .. math:: GSK_{z,n} = \frac{p_n^{gen}}{\sum_{n' \in \mathcal{N}_z} p_{n'}^{gen}}

   * - ``ADJUSTABLE_CAP``
     - Weights buses by the installed capacity of *adjustable* (dispatchable) generators.
       The set of adjustable carriers (e.g. CCGT, coal) is configurable via
       ``gsk_kwargs["ADJUSTABLE_CAP"]["adjustable_carriers"]``.

       .. math:: GSK_{z,n} = \frac{c_n^{adj}}{\sum_{n' \in \mathcal{N}_z} c_{n'}^{adj}}

   * - ``P_NOM``
     - Weights buses by total installed generation capacity :math:`p_n^{nom}`, regardless
       of carrier type.

   * - ``BUS_P``
     - Uses the current nodal net power values from the snapshot (positive = generation
       dominates). Snapshot-dependent.

   * - ``MERIT_ORDER``
     - Distributes the zone's net position change according to the merit-order dispatch
       curve, perturbed by a Gaussian noise of configurable standard deviation. This
       reflects the uncertainty about which units respond to a price signal.

   * - ``ITERATIVE_UNCERTAINTY``
     - Monte-Carlo method that samples :math:`S` scenarios of uncertain renewable
       generation (wind, PV) and residual load. For each scenario an optimal dispatch is
       computed and the resulting per-bus participation factors are averaged to give a
       robust GSK.

   * - ``ITERATIVE_FBMC``
     - Extends ``ITERATIVE_UNCERTAINTY`` with an outer FBMC iteration loop: after the
       first market clearing, the dispatch results update the scenario pool, and the GSK
       is recomputed. The loop repeats until convergence (up to ``max_gsk_iterations``).

Passing a custom GSK
--------------------

A user-defined GSK can be passed as a dict of ``pd.DataFrame`` objects and is automatically
converted to the required ``xarray.DataArray`` format:

.. code-block:: python

   import pandas as pd

   gsk_df = pd.DataFrame(
       {
           "Bus_DE_north": [0.5, 0.0],
           "Bus_DE_south": [0.3, 0.0],
           "Bus_DE_east":  [0.2, 0.0],
           "Bus_FR_1":     [0.0, 0.7],
           "Bus_FR_2":     [0.0, 0.3],
       },
       index=["DE", "FR"],   # rows = zones
   )                          # columns = buses

   gsk = {snapshot: gsk_df for snapshot in nodal_net.snapshots}

   result = zonal_net.fbmc.run(nodal_net, config, gsk=gsk)

Each DataFrame has zones as its index and buses as its columns.
Each zone's row must sum to 1, and buses outside the zone must be 0.

Implementation
--------------

* ``src/fbmc/core/inputs/gsk.py`` – all GSK strategy implementations.
* Entry point: :func:`fbmc.core.inputs.gsk.calculate_gsk`.
* Helper: :func:`fbmc.core.inputs.gsk.gsk_dict_to_xarray`.

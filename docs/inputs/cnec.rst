Critical Network Elements & Contingencies (CNECs)
=================================================

A *Critical Network Element and Contingency* (CNEC) is a pair :math:`(b, c)` where
:math:`b` is a monitored branch and :math:`c` is an outage scenario (or *"no outage"*
for N-0 elements). CNECs determine which flow constraints are included in the FBMC
optimisation.

N-0 CNECs
---------

An N-0 CNEC monitors branch :math:`b` under *normal* operating conditions (no outage).

Only contingencies with a significant impact are kept — those for which the BODF
magnitude exceeds :attr:`~fbmc.settings.FBMCConfig.security_constraint_bodf_size_threshold`
(default ``0.2``). This controls the size of the constraint matrix.

Bridge branches
---------------

Network bridges — branches whose removal disconnects the network — are always excluded
from the CNEC set because no feasible power flow exists after such an outage. These are
identified using a graph-theoretic bridge-finding algorithm before CNEC selection.

CNEC strategies
---------------

The CNEC set is controlled by :attr:`~fbmc.settings.FBMCConfig.cnec_setting`:

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Strategy
     - Description
   * - ``ALL``
     - All non-bridge branches (N-0) plus all significant N-1 pairs (when security
       constraints are enabled).
   * - ``CUSTOM``
     - Only the CNECs directly passed to
       :meth:`~fbmc.accessor.FBMCAccessor.run` or
       :meth:`~fbmc.accessor.FBMCAccessor.create_model`.

CNEC dimensions in the code
-----------------------------

Internally, CNECs are stored as an ``xarray.Coordinates`` object:

* **N-0 CNEC** – a single coordinate ``cnec`` whose values are branch names.
* **N-1 CNEC** – a multi-index coordinate ``(cnec, outage)`` representing the branch /
  outage pair.

The zPTDF and RAM arrays carry this ``cnec`` coordinate, so each constraint row is
self-describing.

Implementation
--------------

* ``src/fbmc/core/inputs/cnec.py``
* ``src/fbmc/core/parameters/bridge_branches.py``
* Key functions:

  - :func:`fbmc.core.inputs.cnec.cnec_router` – top-level dispatcher.
  - :func:`fbmc.core.inputs.cnec.cnec_subnet_router` – per-subnet CNEC selection.

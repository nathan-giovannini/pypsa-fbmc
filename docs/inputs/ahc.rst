Advanced Hybrid Coupling (AHC)
===========================

Through Advanced Hybrid Coupling (AHC) flows coming from HVDC lines are included in the FBMC calculation.

Definition
----------

By calling the function, the nodal network is modified with the introduction of Virtual Hubs. 
Consequently, links are detached from original buses and linkes to newly creted Virtual Hubs.
Virtual Hubs are connected to origial buses with a line with near-zero reactance.

Implementation
--------------

* Entry point: :func:`ahc.ahc_preproc.set_ahc`.

pypsa-fbmc
==========

Flow-Based Market Coupling (FBMC) extension for `PyPSA <https://pypsa.readthedocs.io>`_.

**pypsa-fbmc** implements the flow-based market clearing algorithm used in European capacity
allocation. It takes a nodal power system model (PyPSA Network) alongside a zonal market
model and adds the FBMC capacity constraints derived from the nodal topology.

If you are new to the project, start with :doc:`quickstart`.


.. toctree::
   :maxdepth: 2
   :caption: Getting started

   quickstart

.. toctree::
   :maxdepth: 2
   :caption: Examples

   examples/minimal_example
   examples/custom_cnecs
   examples/fbmc_analysis

.. toctree::
   :maxdepth: 2
   :caption: Inputs

   inputs/gsk
   inputs/cnec
   inputs/base_case
   inputs/config

.. toctree::
   :maxdepth: 2
   :caption: Mathematical concepts

   concepts/fbmc_overview
   concepts/ptdf
   concepts/ram

.. toctree::
   :maxdepth: 2
   :caption: Optional workflows

   workflows/redispatch

.. toctree::
   :maxdepth: 2
   :caption: API reference

   api/run
   api/to_zonal
   api/create_model
   api/solve
   api/results
   api/types
   api/enums

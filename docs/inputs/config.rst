Configuration — FBMCConfig
==========================

.. autoclass:: fbmc.settings.FBMCConfig
   :members:
   :undoc-members:

.. autofunction:: fbmc.settings.merge_config_overrides

Loading configuration
---------------------

The recommended way to create a config is to load a YAML file and then apply any
programmatic overrides:

.. code-block:: python

   from fbmc import FBMCConfig, merge_config_overrides

   config = FBMCConfig.from_base_yaml("config/base_config.yaml")

   config = merge_config_overrides(config, {
       "reliability_margin_factor": 0.10,
       "add_security_constraints": False,
       "solver_kwargs": {"solver_name": "highs"},
   })

YAML format
-----------

The base config YAML file lives at ``config/base_config.yaml``. All top-level keys
correspond directly to :class:`FBMCConfig` field names:

.. code-block:: yaml

   reliability_margin_factor: 0.05
   min_ram: 0.0
   gsk_strategy: ADJUSTABLE_CAP
   gsk_kwargs:
     ADJUSTABLE_CAP:
       adjustable_carriers: [CCGT, coal, lignite, OCGT]
   base_case_strategy: NODAL_OPTIMUM
   add_security_constraints: true
   solver_kwargs:
     solver_name: highs

Parameter reference
-------------------

RAM
~~~

.. list-table::
   :header-rows: 1
   :widths: 30 15 55

   * - Parameter
     - Default
     - Description
   * - ``reliability_margin_factor``
     - ``0.0``
     - FRM as a fraction of branch capacity; reduces available RAM on every CNEC.
       Must be in [0, 1].
   * - ``min_ram``
     - ``0.0``
     - Minimum RAM floor as a fraction of capacity. Ensures cross-zonal headroom
       is always at least this fraction even on heavily loaded branches.

CNEC selection
~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 30 15 55

   * - Parameter
     - Default
     - Description
   * - ``cnec_setting``
     - ``ALL``
     - :class:`~fbmc.enums.CNECStrategy` — ``ALL`` or ``CUSTOM``.
     - How to select CNECs. 
     If ``ALL``, select all lines and transformers. In case ``add_security_constraints`` is True, 
     CNECs are defined as all combinations of branches. 
     If ``CUSTOM``, CNECs must be explicitly passed to
     ``zonal_net.fbmc.run(..., cnecs=...)`` or
     ``zonal_net.fbmc.create_model(..., cnecs=...)``.
     NOTE: 
   * - ``add_security_constraints``
     - ``True``
     - Include N-1 contingency CNECs.
   * - ``security_constraint_bodf_size_threshold``
     - ``0.2``
     - Minimum BODF magnitude to include an N-1 CNEC row.
   * - ``security_constraint_bodf_columnwise_matrix_size_limit``
     - ``5 000 000``
     - Memory guard: maximum number of elements in the BODF matrix column.

GSK
~~~

.. list-table::
   :header-rows: 1
   :widths: 30 15 55

   * - Parameter
     - Default
     - Description
   * - ``gsk_strategy``
     - ``CURRENT_GENERATION``
     - :class:`~fbmc.enums.GSKStrategy` — how bus-level weights are computed.
   * - ``gsk_kwargs``
     - see below
     - Strategy-specific keyword arguments (nested dict keyed by strategy name).

Default ``gsk_kwargs``:

.. code-block:: python

   {
       "ADJUSTABLE_CAP": {
           "adjustable_carriers": ("CCGT", "coal", "lignite", "OCGT", "oil"),
       },
       "ITERATIVE_UNCERTAINTY": {
           "uncertain_carriers": ("offshore-wind", "onshore-wind"),
           "num_scenarios": 100,
           "gen_variation_std_dev": 0.5,
           "load_variation_std_dev": 0.5,
       },
       "ITERATIVE_FBMC": {
           "uncertain_carriers": ("offshore-wind", "onshore-wind"),
           "num_scenarios": 100,
           "max_gsk_iterations": 5,
           "initial_gsk_strategy": "BUS_P",
           "gen_variation_std_dev": 0.5,
           "load_variation_std_dev": 0.5,
       },
       "MERIT_ORDER": {"standard_deviation": 5},
   }

Base case
~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 30 15 55

   * - Parameter
     - Default
     - Description
   * - ``base_case_strategy``
     - ``ZERO_FLOWS``
     - :class:`~fbmc.enums.BaseCaseStrategy` — how the reference operating point is set.
   * - ``marginal_cost_load_shedding``
     - ``1e5``
     - Value of lost load (€/MWh) used in nodal optimisations.

Solver
~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 30 15 55

   * - Parameter
     - Default
     - Description
   * - ``solver_kwargs``
     - ``{"solver_name": "gurobi"}``
     - Passed directly to ``pypsa.Network.optimize``. Use ``"highs"`` for the
       open-source alternative.
   * - ``create_model_kwargs``
     - ``{}``
     - Passed to ``pypsa.Network.optimize.create_model()``.

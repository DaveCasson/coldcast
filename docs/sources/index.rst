Data sources
============

Each page summarizes the upstream service, the YAML configuration block, and the implementation
module. CLI names are lower-case (for example ``coldcast download noaa_hrrr``); several sources
also accept upper-case aliases that match the settings keys.

Gridded NWP from the `NOMADS Grib Filter <https://nomads.ncep.noaa.gov/>`_, station or CSV-heavy
APIs, CDS-style reanalysis jobs, ECMWF open-data retrievals, and Zarr/dynamical.org catalog
outputs all follow this pattern—start from the bundled defaults and adjust templates or model
keys for your workflow.

.. toctree::
   :maxdepth: 1

   noaa_hrrr
   noaa_gfs
   noaa_gefs
   eccc_nwp
   eccc_precip_grid
   eccc_radar
   eccc_api
   alberta_api
   dynamical_catalog
   snotel
   snowcast
   globsnow
   snodas
   era5
   era5_land
   ecmwf_nwp

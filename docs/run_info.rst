Run-info overrides
==================

You can supply **Delft-FEWS** run information so Coldcast uses FEWS reference times, output
directories, and logging settings instead of only the defaults from YAML. Paths may be set on the
CLI (see :doc:`cli`) or in your settings file under keys such as ``run_info_file`` and
``run_info_netcdf``.

Many download jobs **do not** require run info; use these options when you operate inside a
FEWS workflow or need a netCDF ``time0`` (or equivalent) to anchor model cycles.

XML run info (``--run-info-file``)
----------------------------------

When ``run_info_file`` is set (via settings or CLI), :func:`coldcast.run_info.apply_run_info` parses the XML and may set:

* ``start_time``, ``end_time``
* ``work_dir``
* ``output_dir`` from ``destinationDir`` when present

The namespace defaults to ``http://www.wldelft.nl/fews/PI``; override with ``fews_name_space`` in YAML.

NetCDF run info (``--run-info-netcdf``)
---------------------------------------

For a FEWS-style ``runinfo.nc``, :func:`coldcast.run_info.read_netcdf_reference_time` determines the reference time:

1. Prefer variable **``time0``** (CF time units).
2. Else a variable named ``time``, ``TIME``, or ``Time``.
3. Else the first variable with a ``datetime64`` dtype.

The resulting time feeds :mod:`coldcast.time_utils` reference-time logic used when building download jobs. **xarray** is required for this path.

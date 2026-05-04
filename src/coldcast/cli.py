from __future__ import annotations

import argparse
import sys
from typing import Dict, Optional

from .download import download_requests
from .logging_utils import configure_logging
from .settings import load_settings
from .sources import SOURCES, DOWNLOAD_SOURCES
from .sources.eccc_precip_grid import is_hrepa_model, maybe_postprocess_hrepa_fews


SOURCE_CHOICES = [
    "NOAA_HRRR",
    "NOAA_GFS",
    "NOAA_GEFS",
    "ALBERTA_API",
    "ECCC_NWP",
    "ECCC_PRECIP_GRID",
    "ECCC_RADAR",
    "ECCC_API",
    "ECCC_WATER_OFFICE",
    "DYNAMICAL_CATALOG",
    "SNOTEL",
    "SNOWCAST",
    "GLOBSNOW",
    "SNODAS",
    "ERA5",
    "ERA5_LAND",
    "ECMWF_NWP",
]


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--settings", help="Path to YAML settings file")
    parser.add_argument("--run-info-file", help="Optional FEWS run_info XML file")
    parser.add_argument("--run-info-netcdf", help="Optional run info netCDF file (sets reference time)")
    parser.add_argument("--output-dir", help="Override output directory")
    parser.add_argument("--max-threads", type=int, help="Override max threads")
    parser.add_argument("--model", help="Model name (for model-based sources)")
    parser.add_argument("--dry-run", action="store_true", help="Print URLs only, do not download")


def _resolve_model(settings: Dict[str, object], data_source: str, model: Optional[str]) -> Optional[str]:
    if model:
        return model
    source_cfg = settings.get(data_source, {})
    return source_cfg.get("default_model")


def build_arg_parser() -> argparse.ArgumentParser:
    """Return the root CLI parser (used by sphinx-argparse in the docs)."""
    parser = argparse.ArgumentParser(prog="coldcast", description="Coldcast data downloader")
    parser.add_argument(
        "--log-file",
        default="coldcast_download.log",
        metavar="PATH",
        help="Append log messages to this file (default: %(default)s)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    download_parser = subparsers.add_parser("download", help="Download data for a source")
    download_subparsers = download_parser.add_subparsers(dest="data_source", required=True)

    for source in SOURCE_CHOICES:
        source_parser = download_subparsers.add_parser(
            source.lower(),
            help=f"Download {source} data",
            aliases=[source.upper()],
        )
        _add_common_args(source_parser)
        if source in {"ECCC_API", "ALBERTA_API", "ECCC_WATER_OFFICE"}:
            source_parser.add_argument(
                "--stations-csv",
                metavar="PATH",
                help=(
                    "Station mapping CSV override. "
                    "ECCC_API: station_csv_hydro / station_csv_meteo; "
                    "ALBERTA_API: mapping_csv; "
                    "ECCC_WATER_OFFICE: station_csv"
                ),
            )

    return parser


def _run_source(args: argparse.Namespace, data_source: str) -> int:
    bundle = load_settings(
        args.settings,
        output_dir=args.output_dir,
        max_num_threads=args.max_threads,
        run_info_file=args.run_info_file,
        run_info_netcdf=args.run_info_netcdf,
    )
    settings = bundle.settings
    model = _resolve_model(settings, data_source, args.model)

    build_fn = SOURCES[data_source]
    if data_source in {"ECCC_API", "ALBERTA_API", "ECCC_WATER_OFFICE"}:
        stations_csv = getattr(args, "stations_csv", None)
        requests_list = build_fn(settings, model=model, stations_csv=stations_csv)
    elif model:
        requests_list = build_fn(settings, model=model)
    else:
        requests_list = build_fn(settings)

    if args.dry_run:
        for req in requests_list:
            print(req.url)
        return 0

    if data_source in DOWNLOAD_SOURCES:
        if data_source in {"ECCC_API", "ALBERTA_API"}:
            DOWNLOAD_SOURCES[data_source](
                settings,
                data_source=data_source,
                model=model,
                stations_csv=getattr(args, "stations_csv", None),
            )
        elif data_source == "DYNAMICAL_CATALOG":
            DOWNLOAD_SOURCES[data_source](settings, data_source=data_source, model=model)
        else:
            DOWNLOAD_SOURCES[data_source](settings, data_source=data_source)
        return 0

    max_threads = int(settings.get("max_num_threads", 4))
    output_dir = settings["output_dir"]
    download_requests(requests_list, output_dir, max_threads)
    if data_source == "ECCC_PRECIP_GRID" and is_hrepa_model(model):
        maybe_postprocess_hrepa_fews(settings, str(model), requests_list, output_dir)
    return 0


def main() -> None:
    args = build_arg_parser().parse_args()
    configure_logging(log_file=args.log_file)

    if args.command == "download":
        data_source = args.data_source.upper()
        sys.exit(_run_source(args, data_source))


if __name__ == "__main__":
    main()

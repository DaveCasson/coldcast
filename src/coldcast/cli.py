from __future__ import annotations

import argparse
import sys
from typing import Dict, Optional

from .download import download_requests
from .logging_utils import configure_logging
from .settings import load_settings
from .sources import SOURCES, DOWNLOAD_SOURCES


SOURCE_CHOICES = [
    "NOAA_HRRR",
    "NOAA_GFS",
    "NOAA_GEFS",
    "ECCC_NWP",
    "ECCC_PRECIP_GRID",
    "ECCC_RADAR",
    "ECCC_API",
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
    requests_list = build_fn(settings, model=model) if model else build_fn(settings)

    if args.dry_run:
        for req in requests_list:
            print(req.url)
        return 0

    if data_source in DOWNLOAD_SOURCES:
        DOWNLOAD_SOURCES[data_source](settings, data_source=data_source)
        return 0

    max_threads = int(settings.get("max_num_threads", 4))
    output_dir = settings["output_dir"]
    download_requests(requests_list, output_dir, max_threads)
    return 0


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser(prog="coldcast", description="Coldcast data downloader")
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

    args = parser.parse_args()

    if args.command == "download":
        data_source = args.data_source.upper()
        sys.exit(_run_source(args, data_source))


if __name__ == "__main__":
    main()

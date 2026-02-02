from __future__ import annotations

from __future__ import annotations

import logging
import os
import threading
import datetime as dt
import re

from typing import Dict, List, Optional, Tuple

import netCDF4 as nc
import xarray as xr
from ecmwf.opendata import Client

from ..download import DownloadRequest
from ..time_utils import get_reference_time

logger = logging.getLogger("coldcast.ecmwf")


def _ecmwf_retrieve_thread(
    client: Client,
    desc: str,
    retrieve_args: dict,
    output_file: str,
    semaphore: threading.BoundedSemaphore,
    max_threads: int,
) -> bool:
    acquired = False
    try:
        if os.path.isfile(output_file):
            logger.info("File %s already exists (%s)", output_file, desc)
            return False
        semaphore.acquire()
        acquired = True
        logger.info("Starting ECMWF job %s -> %s", desc, output_file)
        client.retrieve(**retrieve_args)
        logger.info("Finished ECMWF job %s -> %s", desc, output_file)
        return True
    except Exception as exc:
        logger.warning("ECMWF job %s failed: %s", desc, exc)
        return False
    finally:
        if acquired:
            semaphore.release()
        active = threading.active_count() - 1
        logger.debug(
            "Threads active = %d, max allowed = %s",
            active,
            max_threads,
        )


def build_requests(settings: Dict[str, object], model: Optional[str] = None) -> List[DownloadRequest]:
    return []


def download(settings: Dict[str, object], data_source: str) -> None:
    model = settings[data_source].get("default_model", "IFS_DET")
    cfg = settings[data_source][model]
    output_dir = settings["output_dir"]
    max_threads = settings.get("max_num_threads", 4)

    delay = int(cfg["delay"])
    lead_time = int(cfg["lead_time"])
    interval = int(cfg["interval"])
    timestep = int(cfg["timestep"])
    first_lead_time = int(cfg.get("first_lead_time", 0))
    parameters = cfg["parameters"]

    use_control = bool(cfg.get("use_control", True))
    control_type = cfg.get("control_type")
    control_number = cfg.get("control_number")

    ensemble_type = cfg.get("ensemble_type")
    ensemble_members = int(cfg.get("ensemble_members", 0))
    ensemble_numbers_cfg = cfg.get("ensemble_numbers")

    model_upper = str(model).upper()
    is_det = ("DET" in model_upper) or ("SINGLE" in model_upper)

    if is_det:
        ensemble_type = None
        ensemble_members = 0
        ensemble_numbers_cfg = None

    semaphore = threading.BoundedSemaphore(max_threads)
    client = Client(source=cfg.get("source", "aws"), model=cfg["ecmwf_model"], resol="0p25")

    latest_kwargs = {}
    stream = cfg.get("stream")
    if stream:
        latest_kwargs["stream"] = stream
    if use_control and control_type:
        latest_kwargs["type"] = control_type
    elif ensemble_type:
        latest_kwargs["type"] = ensemble_type

    latest = client.latest(**latest_kwargs) if latest_kwargs else client.latest()
    run_date = latest.date()
    run_hour = latest.hour

    lead_times = [
        str(lt) for lt in range(first_lead_time, lead_time + timestep, timestep)
    ]

    day_str = run_date.strftime("%Y%m%d")
    hour_str = f"{run_hour:02d}"

    threads = []

    for lead in lead_times:
        step = int(lead)
        ref_time = f"{day_str}{hour_str}0000"
        base = f"{ref_time}-{lead}h-{stream}"

        if use_control and control_type:
            filename = f"{base}-{control_type}.grib2"
            target = os.path.join(output_dir, filename)
            args = {
                "date": run_date,
                "time": run_hour,
                "stream": stream,
                "type": control_type,
                "step": step,
                "param": parameters,
                "target": target,
            }
            if control_number is not None:
                args["number"] = control_number
            desc = f"control-{control_type}"
            thread = threading.Thread(
                target=_ecmwf_retrieve_thread,
                args=(client, desc, args, target, semaphore, max_threads),
            )
            thread.start()
            threads.append(thread)

        if ensemble_type and ensemble_members > 0:
            members = (
                list(ensemble_numbers_cfg)
                if ensemble_numbers_cfg
                else list(range(1, ensemble_members + 1))
            )
            filename = f"{base}-{ensemble_type}.grib2"
            target = os.path.join(output_dir, filename)
            args = {
                "date": run_date,
                "time": run_hour,
                "stream": stream,
                "type": ensemble_type,
                "step": step,
                "param": parameters,
                "target": target,
                "number": members,
            }
            desc = f"ensemble-{ensemble_type}"
            thread = threading.Thread(
                target=_ecmwf_retrieve_thread,
                args=(client, desc, args, target, semaphore, max_threads),
            )
            thread.start()
            threads.append(thread)

    for thread in threads:
        thread.join()

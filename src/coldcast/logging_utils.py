from __future__ import annotations

import logging
import os


def configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def log2xml(log_file: str, xml_file: str) -> None:
    """Convert a text log file to a Delft-FEWS XML diag file."""
    trans = {"WARNING": "2", "ERROR": "1", "INFO": "3", "DEBUG": "4"}
    if not os.path.exists(log_file):
        return

    with open(log_file, "r", encoding="utf-8", errors="replace") as input_handle:
        lines = input_handle.readlines()

    with open(xml_file, "a", encoding="utf-8") as output_handle:
        output_handle.write("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n")
        output_handle.write("<Diag xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" \n")
        output_handle.write("xmlns=\"http://www.wldelft.nl/fews/PI\" xsi:schemaLocation=\"http://www.wldelft.nl/fews/PI \n")
        output_handle.write("http://fews.wldelft.nl/schemas/version1.0/pi-schemas/pi_diag.xsd\" version=\"1.2\">\n")
        for line in lines:
            try:
                parts = line.strip().split(" - ")
                output_handle.write(
                    "<line level=\""
                    + trans[parts[2]]
                    + "\" description=\""
                    + parts[3]
                    + " ["
                    + parts[0]
                    + "]\"/>\n"
                )
            except Exception:
                print("Could not convert line to XML log")
        output_handle.write("</Diag>\n")

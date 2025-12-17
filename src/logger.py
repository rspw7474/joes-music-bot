import logging
import os
import yaml


def configure_logger() -> None:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_file_path = f"{root}/config/logger_config.yaml"
    with open(config_file_path, "r") as f:
        config = yaml.safe_load(f)

    logs_directory_name = config.get("directory_name", "logs")
    logs_file_name = config.get("file_name", "logs.txt")

    logs_directory_path = f"{root}/{logs_directory_name}"
    logs_file_path = f"{logs_directory_path}/{logs_file_name}"

    logs_format = config.get("format", "[%(asctime)s][%(levelname)s] %(message)s")

    os.makedirs(logs_directory_path, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format=logs_format,
        handlers=[logging.StreamHandler(), logging.FileHandler(logs_file_path)]
    )

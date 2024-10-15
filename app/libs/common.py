import json
import logging
import os

import yaml


def read_json_config(general_config_file_path: str):
    """ Read json config file """
    with open(general_config_file_path) as json_file:
        return json.load(json_file)


def read_yaml_config(general_config_file_path: str):
    """ Read json config file """
    with open(general_config_file_path) as json_file:
        return yaml.safe_load(json_file)


class LoggerLevel:
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR


def get_logger(logger, log_file_path: str, level: str = 'DEBUG') -> logging.Logger:
    """ Set logging configuration """

    # Create log directory if not exists
    log_dir = os.path.dirname(log_file_path)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    logger.propagate = False
    logger.setLevel(getattr(LoggerLevel, level))
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger

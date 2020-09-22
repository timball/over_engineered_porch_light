import logging

def set_log_level(level):
    logger = logging.getLogger()
    logger.setLevel(level)
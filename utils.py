import logging
import yaml

def set_log_level(level):
    logger = logging.getLogger()
    logger.setLevel(level)

def load_conf(config):
    with open (config) as f: 
        conf = yaml.load(f, yaml.FullLoader)
    return conf
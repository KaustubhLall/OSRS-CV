import sys
import logging
import threading

class CustomFormatter(logging.Formatter):
    grey = "\x1b[38;20m"
    green = "\x1b[32;1m"
    yellow = "\x1b[33;1m"
    red = "\x1b[31;1m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    format = "(%(filename)s:%(lineno)d)- %(levelname)s - %(message)s "

    FORMATS = {
        logging.DEBUG: grey + format + reset,
        logging.INFO: green + format + reset,
        logging.WARNING: yellow + format + reset,
        logging.ERROR: red + format + reset,
        logging.CRITICAL: bold_red + format + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, style='%')
        return formatter.format(record)


class SingletonLogger:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(SingletonLogger, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self, level=logging.DEBUG, log_to_file=True, filename='logs/application.log'):
        if not self._initialized:
            self._initialized = True
            self._logger = logging.getLogger(__name__)
            self._logger.setLevel(level)
            self._setup_handlers(level, log_to_file, filename)

    def _setup_handlers(self, level, log_to_file, filename):
        formatter = CustomFormatter()
        if log_to_file:
            file_handler = logging.FileHandler(filename, mode='a')
            file_handler.setFormatter(formatter)
            file_handler.setLevel(level)
            self._logger.addHandler(file_handler)
        else:
            stream_handler = logging.StreamHandler(sys.stdout)
            stream_handler.setFormatter(formatter)
            stream_handler.setLevel(level)
            self._logger.addHandler(stream_handler)

    def get_logger(self):
        return self._logger


def setup_logging(level=logging.DEBUG, log_to_file=True, filename='logs/application.log'):
    logger_instance = SingletonLogger(level, log_to_file, filename)
    return logger_instance.get_logger()

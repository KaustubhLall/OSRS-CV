import logging
import os
import sys
import threading

import colorama

colorama.init(autoreset=True)  # Initialize colorama


class CustomFormatter(logging.Formatter):
    """
    Custom logging formatter to add color coding to logs based on log level.
    """

    grey = "\x1b[38;20m"
    light_grey = "\x1b[37;20m"
    white = "\x1b[97;20m"
    green = "\x1b[32;1m"
    yellow = "\x1b[33;1m"
    red = "\x1b[31;1m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"

    base_format = "(%(asctime)s) [%(levelname)s] (%(filename)s:%(lineno)d) - %(message)s"

    FORMATS = {
        logging.DEBUG: light_grey + base_format + reset,
        logging.INFO: white + base_format + reset,
        logging.WARNING: yellow + base_format + reset,
        logging.ERROR: red + base_format + reset,
        logging.CRITICAL: bold_red + base_format + reset
    }

    def format(self, record):
        if sys.stdout.isatty():
            log_fmt = self.FORMATS.get(record.levelno, self.base_format)
        else:
            log_fmt = self.base_format  # No color codes for non-TTY outputs
        formatter = logging.Formatter(log_fmt, datefmt='%Y-%m-%d %H:%M:%S', style='%')
        return formatter.format(record)


class SingletonLogger:
    _instance = None
    _lock = threading.Lock()
    _initialized = False

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if not cls._instance:
                cls._instance = super(SingletonLogger, cls).__new__(cls)
        return cls._instance

    def __init__(self, level=logging.DEBUG, log_to_file=True, filename='logs/application.log',
                 log_to_stdout=False, central_log=True):
        if not self._initialized:
            self._initialized = True
            self._level = level
            self._log_to_file = log_to_file
            self._filename = filename
            self._log_to_stdout = log_to_stdout
            self._central_log = central_log
            self._loggers = {}
            self._setup_logging()

    def _setup_logging(self):
        # Do not use basicConfig to prevent adding default handlers
        self._formatter = CustomFormatter()

        # Suppress logs from external libraries
        self._suppress_external_logs()

        if self._log_to_file and self._central_log:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self._filename), exist_ok=True)
            file_handler = logging.FileHandler(self._filename, mode='a')
            file_handler.setFormatter(self._formatter)
            file_handler.setLevel(self._level)
            root_logger = logging.getLogger()
            root_logger.setLevel(self._level)
            root_logger.addHandler(file_handler)

    def _suppress_external_logs(self):
        external_loggers = ['PIL', 'urllib3']

        for logger_name in external_loggers:
            logging.getLogger(logger_name).setLevel(logging.WARNING)

    def get_logger(self, module_name, log_to_file=None, log_to_stdout=None, central_log=None):

        if module_name in self._loggers:
            return self._loggers[module_name]
        else:
            logger = logging.getLogger(module_name)
            logger.setLevel(self._level)

            # Prevent log messages from propagating to the root logger
            logger.propagate = False

            # Determine whether to log to stdout
            if log_to_stdout is None:
                log_to_stdout = self._log_to_stdout

            if log_to_stdout:
                stream_handler = logging.StreamHandler(sys.stdout)
                stream_handler.setFormatter(self._formatter)
                stream_handler.setLevel(self._level)
                logger.addHandler(stream_handler)

            # Determine whether to log to file
            if log_to_file is None:
                log_to_file = self._log_to_file

            if central_log is None:
                central_log = self._central_log

            if log_to_file:
                if central_log:
                    # Central log is already set up at root logger
                    pass
                else:
                    # Create a sub-log file for this module
                    module_filename = f'logs/{module_name.replace(".", "_")}.log'
                    os.makedirs(os.path.dirname(module_filename), exist_ok=True)
                    file_handler = logging.FileHandler(module_filename, mode='a')
                    file_handler.setFormatter(self._formatter)
                    file_handler.setLevel(self._level)
                    logger.addHandler(file_handler)

            self._loggers[module_name] = logger
            return logger


def setup_logging(level=logging.DEBUG, log_to_file=True, filename='logs/application.log',
                  log_to_stdout=False, central_log=True):
    logger_manager = SingletonLogger(level, log_to_file, filename, log_to_stdout, central_log)
    return logger_manager

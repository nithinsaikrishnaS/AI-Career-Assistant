import logging
import sys
import os

def setup_logger(name="AI-Job-Aggregator"):
    # Clear existing handlers
    logger = logging.getLogger(name)
    if logger.hasHandlers():
        logger.handlers.clear()
        
    logger.setLevel(logging.INFO)
    
    # Format: [2026-04-14 01:32:19] [INFO] [main] - Message
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] [%(name)s] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Avoid propagation to root to prevent duplicate logs
    logger.propagate = False
    
    return logger

# Singletons for main modules
def get_logger(module_name):
    return setup_logger(module_name)

"""
Logging configuration using loguru.
"""
import sys
from pathlib import Path
from loguru import logger


def setup_logging(
    log_file: str = "logs/xhs.log",
    level: str = "INFO",
    rotation: str = "10 MB",
    retention: str = "7 days",
):
    """Setup application logging."""
    # Remove default handler
    logger.remove()
    
    # Ensure log directory exists
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    
    # Add console handler with colors
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=level,
        colorize=True,
    )
    
    # Add file handler with rotation
    logger.add(
        log_file,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level=level,
        rotation=rotation,
        retention=retention,
        encoding="utf-8",
    )
    
    logger.info("Logging initialized")
    return logger

import sys

from loguru import logger


def configure_logging(level: str) -> None:
    """Configure one concise Loguru sink for the application process."""

    logger.remove()
    logger.add(
        sys.stderr,
        level=level.upper(),
        format=("{time:YYYY-MM-DDTHH:mm:ss.SSSZ} | {level} | {message} | context={extra}"),
        backtrace=False,
        diagnose=False,
    )

"""
Exceptions raised while talking to the scanner.
"""


class ScannerError(Exception):
    """
    Base class for every error this package raises.
    """


class ScannerNotFoundError(ScannerError):
    """
    No serial port could be picked for the scanner.
    """


class ScannerTimeoutError(ScannerError, TimeoutError):
    """
    The scanner did not finish a response before the read timeout.
    """


class CommandError(ScannerError):
    """
    The scanner rejected the command's format or a value (``ERR``).
    """


class CommandRejectedError(ScannerError):
    """
    The command is not allowed right now (``NG``).

    Most programming commands need program mode, and some commands are
    refused while the scanner is in a menu or in the middle of direct
    entry.
    """


class FramingError(ScannerError):
    """
    The scanner saw a serial framing error (``FER``).

    Check that the baud rate matches the scanner's setting.
    """


class OverrunError(ScannerError):
    """
    The scanner's receive buffer overran (``ORER``).
    """


class UnexpectedResponseError(ScannerError):
    """
    The response did not match the format the protocol specifies.
    """


class NoFreeMemoryError(ScannerError):
    """
    No free memory blocks for a new system, group or channel.
    """

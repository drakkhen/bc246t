"""
End-to-end tests through a real ``serial.Serial`` on a pseudo-terminal.

The simulated scanner answers on the far side of the pty, so these
tests exercise pyserial itself: opening the port, the timeout property
and ``read_until``.
"""

import os
import select
import sys
import threading
from collections.abc import Iterator

import pytest

from bc246t import Scanner, ScannerTimeoutError, SystemType

from .simulator import SimulatedScanner

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="needs a POSIX pty")


class _PtyScanner:
    """
    Serve the simulator on the controlling side of a pseudo-terminal.
    """

    def __init__(self, simulator: SimulatedScanner) -> None:
        import pty
        import tty

        self.simulator = simulator
        self.silent = False
        self._controller, device = pty.openpty()
        tty.setraw(device)
        self.port = os.ttyname(device)
        self._device = device
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self) -> None:
        buffer = b""
        while not self._stop.is_set():
            ready, _, _ = select.select([self._controller], [], [], 0.05)
            if not ready:
                continue
            buffer += os.read(self._controller, 256)
            while b"\r" in buffer:
                line, buffer = buffer.split(b"\r", 1)
                if self.silent:
                    continue
                self.simulator.write(line + b"\r")
                os.write(self._controller, self.simulator.read_until())

    def close(self) -> None:
        # Closing a pty while another thread reads it blocks on macOS,
        # so stop the thread first.
        self._stop.set()
        self._thread.join()
        os.close(self._controller)
        os.close(self._device)


@pytest.fixture
def pty_scanner() -> Iterator[_PtyScanner]:
    server = _PtyScanner(SimulatedScanner())
    yield server
    server.close()


def test_commands_round_trip_through_pyserial(pty_scanner: _PtyScanner) -> None:
    with Scanner.open(pty_scanner.port, timeout=2) as scanner:
        assert scanner.get_model() == "BC246T"
        with scanner.program_mode():
            index = scanner.create_system(SystemType.CONVENTIONAL)
            scanner.set_system_info(index, name="Serial test")
            assert scanner.get_system_info(index).name == "Serial test"


def test_clear_memory_restores_the_port_timeout(pty_scanner: _PtyScanner) -> None:
    with Scanner.open(pty_scanner.port, timeout=1.5) as scanner, scanner.program_mode():
        scanner.clear_memory()

        assert scanner._transport.timeout == 1.5


def test_silence_times_out(pty_scanner: _PtyScanner) -> None:
    pty_scanner.silent = True

    with (
        Scanner.open(pty_scanner.port, timeout=0.2) as scanner,
        pytest.raises(ScannerTimeoutError),
    ):
        scanner.get_model()

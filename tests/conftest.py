"""
Shared fixtures.
"""

import pytest

from bc246t import Scanner

from .simulator import SimulatedScanner


@pytest.fixture
def simulator() -> SimulatedScanner:
    return SimulatedScanner()


@pytest.fixture
def simulated(simulator: SimulatedScanner) -> Scanner:
    return Scanner(simulator)

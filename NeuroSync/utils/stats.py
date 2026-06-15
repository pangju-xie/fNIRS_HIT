from dataclasses import dataclass, field
from enum import IntEnum, IntFlag
from typing import List, Tuple
import time


class SensorTypes(IntFlag):
    NotInit = 0
    EEG = 1
    SEMG = 2
    EEG_SEMG = 3
    FNIRS = 4
    EEG_FNIRS = 5
    SEMG_FNIRS = 6
    EEG_SEMG_FNIRS = 7


class Commands(IntEnum):
    CONNECT = 0xA0
    DISCONNECT = 0xA1
    SAMPLE_RATE = 0xB0
    CHANNEL_CONFIG = 0xB1
    BATTERY_QUERY = 0xB2
    START_SAMPLE = 0xC0
    STOP_SAMPLE = 0xC1
    QUALITY_TEST = 0xC2
    DATA_PATCHING = 0xC3


class UplinkFrameCodes(IntEnum):
    STREAM_DATA = 0xD0
    PATCHED_DATA = 0xD1
    QUALITY_DATA = 0xD2


class AcquisitionSessionType(IntEnum):
    IDLE = 0
    QUALITY_TEST = 1
    LIVE_ACQUIRE = 2


class DisplayMode(IntEnum):
    RAW = 0
    HEMO = 1


class WorkflowStates(IntEnum):
    DISCONNECTED = 0
    CONNECTED = 1
    CONFIGURED = 2
    QUALIFIED = 3
    ACQUIRED = 4
    ANALYZED = 5


@dataclass
class PendingCommand:
    command: Commands
    packet: bytes
    target_ip: str
    timestamp: float = field(default_factory=time.time)
    retry_count: int = 0


@dataclass
class Device:
    ip: str
    id: List[int]
    type: SensorTypes
    port: int

    def __hash__(self):
        return hash((self.ip, tuple(self.id), self.type, self.port))


class SystemState:
    def __init__(self):
        self._workflow = WorkflowStates.DISCONNECTED

    @property
    def workflow(self) -> WorkflowStates:
        return self._workflow

    def advance_workflow(self, target_state: WorkflowStates) -> Tuple[bool, str]:
        if target_state == self._workflow:
            return True, "State unchanged"
        if target_state < self._workflow:
            self._workflow = target_state
            return True, f"State rolled back to {target_state.name}"
        if target_state.value == self._workflow.value + 1:
            self._workflow = target_state
            return True, f"State advanced to {target_state.name}"

        next_required_state = WorkflowStates(self._workflow.value + 1).name
        return False, f"Invalid transition, expected {next_required_state} first"

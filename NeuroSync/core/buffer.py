import logging
import os
from collections import defaultdict

from PyQt5.QtCore import QObject, pyqtSignal

from utils.stats import AcquisitionSessionType, DisplayMode, SensorTypes

logger = logging.getLogger(__name__)


class DataBufferManager(QObject):
    signal_batch_patched_done = pyqtSignal()
    signal_quality_updated = pyqtSignal(SensorTypes, dict)
    signal_raw_stream = pyqtSignal(object, list)

    PATCH_BATCH_SIZE = 16

    def __init__(self, system_state):
        super().__init__()
        self.system_state = system_state
        self.processors = {}
        self.missing_packets_dict = defaultdict(list)
        self.current_patching_batch = []
        self.current_round_task_queue = []
        self.session_type = AcquisitionSessionType.IDLE
        self.display_mode = DisplayMode.HEMO
        self.is_recording = False
        self.raw_log_file = None
        self.session_dir = ""
        self.file_basename = ""

    def init_processors(self, sensor_mode: SensorTypes):
        self.processors.clear()

        if sensor_mode.value & SensorTypes.FNIRS.value:
            from physioSignal.fnirs import fNIRSProcessor

            self.processors[SensorTypes.FNIRS] = fNIRSProcessor()
            logger.info("已挂载 fNIRS 处理器。")

        if sensor_mode.value & SensorTypes.EEG.value:
            from physioSignal.eeg import EegProcessor

            self.processors[SensorTypes.EEG] = EegProcessor()
            logger.info("已挂载 EEG 处理器。")

    def reset_all(self):
        for processor in self.processors.values():
            if hasattr(processor, "reset_data"):
                processor.reset_data()
        self.missing_packets_dict.clear()
        self.current_patching_batch.clear()
        self.current_round_task_queue.clear()
        self.session_type = AcquisitionSessionType.IDLE
        self.is_recording = False
        if self.raw_log_file:
            self.raw_log_file.close()
            self.raw_log_file = None

    def set_session_type(self, session_type: AcquisitionSessionType):
        self.session_type = session_type

    def set_display_mode(self, display_mode: DisplayMode):
        self.display_mode = display_mode

    def set_recording_enabled(self, enabled: bool):
        self.is_recording = enabled

    def start_recording(self, save_dir: str, file_basename: str):
        self.session_dir = save_dir
        self.file_basename = file_basename
        log_path = os.path.join(save_dir, "raw_payload_backup.bin")
        self.raw_log_file = open(log_path, "wb")
        self.missing_packets_dict.clear()
        self.current_patching_batch.clear()
        self.current_round_task_queue.clear()
        for processor in self.processors.values():
            if hasattr(processor, "reset_data"):
                processor.reset_data()
        self.is_recording = True

    def stop_recording(self):
        if self.raw_log_file:
            self.raw_log_file.flush()
            self.raw_log_file.close()
            self.raw_log_file = None
        self.is_recording = False

    def _get_processor(self, sensor_type_val: int):
        try:
            target_sensor = SensorTypes(sensor_type_val)
        except ValueError:
            return None, None
        if target_sensor not in self.processors:
            return target_sensor, None
        processor = self.processors[target_sensor]
        if not getattr(processor, "is_configured", True):
            return target_sensor, None
        return target_sensor, processor

    def handle_quality_data(self, sensor_type_val: int, packet_id: int, raw_payload: list):
        target_sensor, processor = self._get_processor(sensor_type_val)
        if target_sensor is None or processor is None:
            return
        if self.session_type != AcquisitionSessionType.QUALITY_TEST:
            return

        if hasattr(processor, "process_quality_packet"):
            quality_result = processor.process_quality_packet(packet_id, raw_payload)
            if quality_result is not None:
                self.signal_quality_updated.emit(target_sensor, quality_result)

    def handle_live_data(self, sensor_type_val: int, packet_id: int, raw_payload: list):
        target_sensor, processor = self._get_processor(sensor_type_val)
        if target_sensor is None or processor is None:
            return
        if self.session_type != AcquisitionSessionType.LIVE_ACQUIRE:
            return

        if self.is_recording and self.raw_log_file:
            self.raw_log_file.write(bytes(raw_payload))

        missing_ids = []
        parsed_values = []
        if hasattr(processor, "process_live_packet"):
            missing_ids, parsed_values = processor.process_live_packet(
                packet_id,
                raw_payload,
                self.display_mode,
                self.is_recording,
            )

        if parsed_values:
            self.signal_raw_stream.emit(target_sensor, parsed_values)

        if self.is_recording and missing_ids:
            self.missing_packets_dict[target_sensor].extend(missing_ids)

    def handle_patched_data(self, sensor_type_val: int, packet_id: int, patched_data: list):
        target_sensor, processor = self._get_processor(sensor_type_val)
        if target_sensor is None or processor is None:
            return

        if hasattr(processor, "patch_packet"):
            processor.patch_packet(packet_id, patched_data)

        if packet_id in self.missing_packets_dict[target_sensor]:
            self.missing_packets_dict[target_sensor].remove(packet_id)
        if packet_id in self.current_patching_batch:
            self.current_patching_batch.remove(packet_id)

        if len(self.current_patching_batch) == 0:
            self.signal_batch_patched_done.emit()

    def get_total_missing_count(self) -> int:
        return sum(len(ids) for ids in self.missing_packets_dict.values())

    def prepare_patching_round(self):
        self.current_round_task_queue.clear()
        for s_type, ids in self.missing_packets_dict.items():
            if not ids:
                continue
            for i in range(0, len(ids), self.PATCH_BATCH_SIZE):
                batch = ids[i : i + self.PATCH_BATCH_SIZE]
                self.current_round_task_queue.append((s_type, batch))

    def pop_next_patch_batch(self) -> tuple:
        if self.current_round_task_queue:
            s_type, batch = self.current_round_task_queue.pop(0)
            self.current_patching_batch = batch.copy()
            return s_type, batch
        return None, []

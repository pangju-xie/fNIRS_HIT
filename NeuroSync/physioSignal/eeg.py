import csv
import logging
import os

import numpy as np


logger = logging.getLogger(__name__)


class EegProcessor:
    """EEG signal processor for quality, live acquisition, patching, and CSV export."""

    BYTES_PER_SAMPLE = 3
    STATUS_BYTES = 3
    SAMPLES_PER_PACKET = 10
    ADC_SIGN_BIT = 0x800000
    ADC_POSITIVE_FULL_SCALE = 0x7FFFFF
    ADS1299_INTERNAL_VREF_UV = 4500000.0
    ADS1299_DEFAULT_PGA_GAIN = 24.0
    ADS1299_DEFAULT_LEADOFF_CURRENT_UA = 6.0
    QUALITY_WINDOW_SECONDS = 1.0
    QUALITY_REFRESH_HZ = 10.0

    def __init__(self, sample_rate=500):
        self.sample_rate = sample_rate
        self.channels = []
        self.channel_num = 0
        self.eeg_montage = {}
        self.channel_coords = {}
        self.montage_dict = {}
        self.is_configured = False
        self.ads1299_vref_uv = self.ADS1299_INTERNAL_VREF_UV
        self.ads1299_gain = self.ADS1299_DEFAULT_PGA_GAIN
        self.ads1299_leadoff_current_ua = self.ADS1299_DEFAULT_LEADOFF_CURRENT_UA
        self.last_status_bytes = []
        self.reset_data()

    def get_channels(self) -> list:
        return self.channels

    def get_display_channels(self) -> list:
        if not self.channels:
            return []
        return [self.eeg_montage.get(alias, alias) or alias for alias in self.channels]

    def get_sample_rate(self) -> int:
        return self.sample_rate

    def set_sample_rate(self, sample_rate: int):
        self.sample_rate = sample_rate
        logger.info("EEG 采样率已更新：%s Hz", self.sample_rate)
        if self.channel_num > 0:
            self.reset_data()
            self.reset_quality_data()

    def set_config(self, montage_dict: dict):
        self.montage_dict = montage_dict
        self.channels = montage_dict.get("eeg_channels", [])
        self.channel_num = montage_dict.get("eeg_num", len(self.channels))
        self.ads1299_vref_uv = float(montage_dict.get("ads1299_vref_uv", self.ADS1299_INTERNAL_VREF_UV))
        self.ads1299_gain = float(montage_dict.get("ads1299_gain", self.ADS1299_DEFAULT_PGA_GAIN))
        self.ads1299_leadoff_current_ua = float(
            montage_dict.get("ads1299_leadoff_current_ua", self.ADS1299_DEFAULT_LEADOFF_CURRENT_UA)
        )

        self.eeg_montage.clear()
        self.channel_coords.clear()
        self.is_configured = False

        if self.channel_num <= 0:
            logger.warning("蒙太奇配置中没有有效的 EEG 通道。")
            return

        details_dict = montage_dict.get("eeg_details", {})
        for e_alias in self.channels:
            e_info = details_dict.get(e_alias, {})
            self.eeg_montage[e_alias] = e_info.get("standard_name", "")
            self.channel_coords[e_alias] = e_info.get("coord", (0, 0))

        self.reset_data()
        self.reset_quality_data()
        self.is_configured = True

        logger.info("EEG 处理器配置完成。")
        logger.info("通道数量：%s", self.channel_num)
        logger.info("通道列表：%s", self.channels)
        logger.info("ADS1299 参考电压：%s uV，增益：%s", self.ads1299_vref_uv, self.ads1299_gain)
        logger.info("EEG 阻抗换算参数：lead-off 电流=%s uA", self.ads1299_leadoff_current_ua)
        logger.info("EEG 数据封包规则：每包固定 %s 个采样点。", self.SAMPLES_PER_PACKET)

    def reset_data(self):
        self.max_capacity = max(int(self.sample_rate) * 3600, 1)
        self.current_idx = 0
        self.time = np.full(self.max_capacity, np.nan, dtype=np.float64)
        self.packet_ids = np.full(self.max_capacity, -1, dtype=np.int32)
        self.raw = np.full((self.max_capacity, self.channel_num), np.nan, dtype=np.float32)

    def reset_quality_data(self):
        self.impedance = np.zeros(self.channel_num, dtype=np.float32)
        self.lead_off_p = np.zeros(self.channel_num, dtype=bool)
        self.lead_off_n = np.zeros(self.channel_num, dtype=bool)
        self.lead_off_any = np.zeros(self.channel_num, dtype=bool)
        self.quality_window_size = max(int(round(self.QUALITY_WINDOW_SECONDS * self.sample_rate)), 1)
        self.quality_buffer = np.zeros((self.quality_window_size, self.channel_num), dtype=np.float32)
        packet_rate = max(float(self.sample_rate) / float(self.SAMPLES_PER_PACKET), 1.0)
        self.quality_step_packets = max(int(round(packet_rate / self.QUALITY_REFRESH_HZ)), 1)
        self.quality_sample_count = 0
        self.quality_packet_count = 0

    def _expand_capacity(self):
        old_capacity = self.max_capacity
        self.max_capacity *= 2
        self.time = np.pad(self.time, (0, self.max_capacity - old_capacity), constant_values=np.nan)
        self.packet_ids = np.pad(self.packet_ids, (0, self.max_capacity - old_capacity), constant_values=-1)
        self.raw = np.pad(self.raw, ((0, self.max_capacity - old_capacity), (0, 0)), constant_values=np.nan)

    def process_quality_packet(self, packet_id: int, data_bytes: list):
        del packet_id
        if not self.is_configured or self.channel_num == 0:
            return None

        quality_samples = self._decode_quality_voltage_values(data_bytes)
        if quality_samples.size == 0:
            return None
        lead_off_p, lead_off_n = self._decode_quality_leadoff(data_bytes)
        if lead_off_p.size == self.channel_num:
            self.lead_off_p = lead_off_p
            self.lead_off_n = lead_off_n
            self.lead_off_any = np.logical_or(lead_off_p, lead_off_n)

        self._append_quality_samples(quality_samples)
        self.quality_packet_count += 1
        if self.quality_packet_count < self.quality_step_packets:
            return None
        self.quality_packet_count = 0

        valid_window = self.quality_buffer[: self.quality_sample_count]
        impedance_values = self._calculate_impedance_kohm(valid_window)
        if impedance_values.size == 0:
            return None

        self.impedance = impedance_values.astype(np.float32)

        quality_dict = {}
        for idx, channel_name in enumerate(self.channels):
            quality_dict[channel_name] = {
                "impedance_kohm": float(self.impedance[idx]),
                "lead_off": bool(self.lead_off_any[idx]),
                "lead_off_p": bool(self.lead_off_p[idx]),
                "lead_off_n": bool(self.lead_off_n[idx]),
            }
        return quality_dict

    def process_live_packet(self, packet_id: int, data_bytes: list, display_mode, record_enabled: bool):
        del display_mode
        if not self.is_configured or self.channel_num == 0:
            return [], []

        voltage_values = self._decode_voltage_values(data_bytes)
        if voltage_values.size == 0:
            return [], []

        batch_size = self.SAMPLES_PER_PACKET
        missing_ids = []

        if record_enabled:
            if self.current_idx >= self.max_capacity - max(batch_size, 5000):
                self._expand_capacity()

            if self.current_idx > 0:
                last_id = int(self.packet_ids[self.current_idx - 1])
                if packet_id > last_id + 1:
                    missing_count = packet_id - (last_id + 1)
                    if missing_count > 5000:
                        missing_count = 10

                    missing_ids = list(range(last_id + 1, last_id + 1 + missing_count))
                    missing_samples = missing_count * self.SAMPLES_PER_PACKET
                    start_idx = self.current_idx
                    end_idx = self.current_idx + missing_samples
                    self.raw[start_idx:end_idx] = self.raw[self.current_idx - 1]

                    write_idx = start_idx
                    for missing_id in missing_ids:
                        for _ in range(self.SAMPLES_PER_PACKET):
                            self.packet_ids[write_idx] = missing_id
                            self.time[write_idx] = write_idx / self.sample_rate
                            write_idx += 1

                    self.current_idx += missing_samples

            start_idx = self.current_idx
            end_idx = self.current_idx + batch_size
            self.raw[start_idx:end_idx] = voltage_values
            self.packet_ids[start_idx:end_idx] = packet_id
            self.time[start_idx:end_idx] = np.arange(start_idx, end_idx, dtype=np.float64) / self.sample_rate
            self.current_idx = end_idx

        return missing_ids, voltage_values.tolist()

    def patch_packet(self, packet_id: int, data_bytes: list):
        if self.current_idx == 0 or self.channel_num == 0:
            return

        indices = np.where(self.packet_ids[: self.current_idx] == packet_id)[0]
        if len(indices) == 0:
            logger.debug("丢弃过期 EEG 补包：%s", packet_id)
            return

        voltage_values = self._decode_voltage_values(data_bytes)
        if voltage_values.size == 0:
            return

        write_count = min(len(indices), self.SAMPLES_PER_PACKET)
        self.raw[indices[:write_count]] = voltage_values[:write_count]
        logger.info("EEG 补包已恢复：%s（样本数=%s）", packet_id, write_count)

    def _append_quality_samples(self, quality_samples: np.ndarray):
        sample_count = quality_samples.shape[0]
        if sample_count >= self.quality_window_size:
            self.quality_buffer[:] = quality_samples[-self.quality_window_size :]
            self.quality_sample_count = self.quality_window_size
            return

        keep_count = min(self.quality_sample_count, self.quality_window_size - sample_count)
        if keep_count > 0:
            start = self.quality_sample_count - keep_count
            self.quality_buffer[:keep_count] = self.quality_buffer[start : self.quality_sample_count]
        self.quality_buffer[keep_count : keep_count + sample_count] = quality_samples
        self.quality_sample_count = min(keep_count + sample_count, self.quality_window_size)

    def _decode_quality_voltage_values(self, data_bytes: list) -> np.ndarray:
        counts = self._decode_quality_counts(data_bytes)
        if counts.size == 0:
            return np.array([], dtype=np.float32)
        return self.adc_to_voltage(counts)

    def _decode_voltage_values(self, data_bytes: list) -> np.ndarray:
        counts = self._decode_24bit_counts(data_bytes)
        if counts.size == 0:
            return np.array([], dtype=np.float32)
        return self.adc_to_voltage(counts)

    def _decode_24bit_counts(self, data_bytes: list) -> np.ndarray:
        if self.channel_num == 0:
            return np.array([], dtype=np.int32)

        sample_bytes = self.channel_num * self.BYTES_PER_SAMPLE
        frame_bytes = self.STATUS_BYTES + sample_bytes
        expected_payload_len = self.SAMPLES_PER_PACKET * frame_bytes
        payload = list(data_bytes)

        if len(payload) != expected_payload_len:
            logger.warning(
                "EEG 数据包长度异常：当前=%s 字节，期望=%s 字节。",
                len(payload),
                expected_payload_len,
            )
            return np.array([], dtype=np.int32)

        counts = np.zeros((self.SAMPLES_PER_PACKET, self.channel_num), dtype=np.int32)
        for frame_idx in range(self.SAMPLES_PER_PACKET):
            frame_offset = frame_idx * frame_bytes
            status_start = frame_offset
            data_start = frame_offset + self.STATUS_BYTES
            if frame_idx == self.SAMPLES_PER_PACKET - 1:
                self.last_status_bytes = payload[status_start:data_start]

            frame_payload = payload[data_start : data_start + sample_bytes]
            counts[frame_idx] = self._decode_counts_from_frame(frame_payload)

        return counts

    def _decode_quality_counts(self, data_bytes: list) -> np.ndarray:
        if self.channel_num == 0:
            return np.array([], dtype=np.int32)

        sample_bytes = self.channel_num * self.BYTES_PER_SAMPLE
        frame_bytes = self.STATUS_BYTES + sample_bytes
        payload = list(data_bytes)

        if len(payload) == self.SAMPLES_PER_PACKET * frame_bytes:
            counts = np.zeros((self.SAMPLES_PER_PACKET, self.channel_num), dtype=np.int32)
            for frame_idx in range(self.SAMPLES_PER_PACKET):
                frame_offset = frame_idx * frame_bytes
                data_start = frame_offset + self.STATUS_BYTES
                if frame_idx == self.SAMPLES_PER_PACKET - 1:
                    self.last_status_bytes = payload[frame_offset:data_start]
                frame_payload = payload[data_start : data_start + sample_bytes]
                counts[frame_idx] = self._decode_counts_from_frame(frame_payload)
            return counts

        if len(payload) == self.SAMPLES_PER_PACKET * sample_bytes:
            counts = np.zeros((self.SAMPLES_PER_PACKET, self.channel_num), dtype=np.int32)
            for frame_idx in range(self.SAMPLES_PER_PACKET):
                frame_offset = frame_idx * sample_bytes
                frame_payload = payload[frame_offset : frame_offset + sample_bytes]
                counts[frame_idx] = self._decode_counts_from_frame(frame_payload)
            return counts

        if len(payload) == sample_bytes + self.STATUS_BYTES:
            self.last_status_bytes = payload[: self.STATUS_BYTES]
            payload = payload[self.STATUS_BYTES :]
            return self._decode_counts_from_frame(payload)[np.newaxis, :]

        if len(payload) == sample_bytes:
            return self._decode_counts_from_frame(payload)[np.newaxis, :]

        logger.warning(
            "EEG 质量包长度异常：当前=%s 字节，期望=%s、%s、%s 或 %s 字节。",
            len(payload),
            self.SAMPLES_PER_PACKET * sample_bytes,
            self.SAMPLES_PER_PACKET * frame_bytes,
            sample_bytes,
            sample_bytes + self.STATUS_BYTES,
        )
        return np.array([], dtype=np.int32)

    def _decode_quality_leadoff(self, data_bytes: list):
        if self.channel_num == 0:
            return np.array([], dtype=bool), np.array([], dtype=bool)

        sample_bytes = self.channel_num * self.BYTES_PER_SAMPLE
        frame_bytes = self.STATUS_BYTES + sample_bytes
        payload = list(data_bytes)

        if len(payload) == self.SAMPLES_PER_PACKET * frame_bytes:
            lead_off_p = np.zeros(self.channel_num, dtype=bool)
            lead_off_n = np.zeros(self.channel_num, dtype=bool)
            for frame_idx in range(self.SAMPLES_PER_PACKET):
                frame_offset = frame_idx * frame_bytes
                status_bytes = payload[frame_offset : frame_offset + self.STATUS_BYTES]
                p_bits, n_bits = self._decode_leadoff_bits(status_bytes)
                lead_off_p = np.logical_or(lead_off_p, p_bits)
                lead_off_n = np.logical_or(lead_off_n, n_bits)
            return lead_off_p, lead_off_n

        if len(payload) == sample_bytes + self.STATUS_BYTES:
            return self._decode_leadoff_bits(payload[: self.STATUS_BYTES])

        return np.zeros(self.channel_num, dtype=bool), np.zeros(self.channel_num, dtype=bool)

    def _decode_leadoff_bits(self, status_bytes):
        if len(status_bytes) != self.STATUS_BYTES:
            return np.zeros(self.channel_num, dtype=bool), np.zeros(self.channel_num, dtype=bool)

        self.last_status_bytes = list(status_bytes)
        status_word = (int(status_bytes[0]) << 16) | (int(status_bytes[1]) << 8) | int(status_bytes[2])
        loff_statp = (status_word >> 12) & 0xFF
        loff_statn = (status_word >> 4) & 0xFF

        lead_off_p = np.zeros(self.channel_num, dtype=bool)
        lead_off_n = np.zeros(self.channel_num, dtype=bool)
        for ch_idx in range(min(self.channel_num, 8)):
            lead_off_p[ch_idx] = bool((loff_statp >> ch_idx) & 0x01)
            lead_off_n[ch_idx] = bool((loff_statn >> ch_idx) & 0x01)
        return lead_off_p, lead_off_n

    def _decode_counts_from_frame(self, payload: list) -> np.ndarray:
        expected_len = self.channel_num * self.BYTES_PER_SAMPLE
        if len(payload) != expected_len:
            logger.warning("EEG 帧数据长度异常：当前=%s 字节，期望=%s 字节。", len(payload), expected_len)
            return np.array([], dtype=np.int32)

        counts = np.zeros(self.channel_num, dtype=np.int32)
        for ch_idx in range(self.channel_num):
            base = ch_idx * self.BYTES_PER_SAMPLE
            raw_val = (
                (int(payload[base]) << 16)
                | (int(payload[base + 1]) << 8)
                | int(payload[base + 2])
            )
            if raw_val & self.ADC_SIGN_BIT:
                raw_val -= 1 << 24
            counts[ch_idx] = raw_val
        return counts

    def _calculate_impedance_kohm(self, voltage_window_uv: np.ndarray) -> np.ndarray:
        if voltage_window_uv.size == 0:
            return np.array([], dtype=np.float32)

        peak_to_peak_uv = np.max(voltage_window_uv, axis=0) - np.min(voltage_window_uv, axis=0)
        current_ua = max(self.ads1299_leadoff_current_ua, 1e-6)
        impedance_ohm = np.maximum(peak_to_peak_uv, 0.0) / (2.0 * current_ua)
        return (impedance_ohm / 1000.0).astype(np.float32)

    def adc_to_voltage(self, counts: np.ndarray) -> np.ndarray:
        scale = (2.0 * self.ads1299_vref_uv / self.ads1299_gain) / float(1 << 24)
        return counts.astype(np.float32) * scale

    def export_csv(self, save_dir: str, file_basename: str, start_time, patient_info: dict = None):
        if self.current_idx == 0:
            logger.warning("没有记录到 EEG 数据，跳过 CSV 导出。")
            return

        data_path = os.path.join(save_dir, f"{file_basename}_eeg_data.csv")
        meta_path = os.path.join(save_dir, f"{file_basename}_eeg_meta.csv")

        valid_packet_ids = self.packet_ids[: self.current_idx]
        valid_time = self.time[: self.current_idx]
        valid_raw = self.raw[: self.current_idx]

        with open(data_path, "w", newline="", encoding="utf-8-sig") as data_file:
            writer = csv.writer(data_file)
            writer.writerow(["packet_id", "time_sec", *self.channels])
            for packet_id, time_sec, row in zip(valid_packet_ids, valid_time, valid_raw):
                writer.writerow([int(packet_id), float(time_sec), *[float(val) for val in row]])

        with open(meta_path, "w", newline="", encoding="utf-8-sig") as meta_file:
            writer = csv.writer(meta_file)
            writer.writerow(["key", "value"])
            writer.writerow(["device_type", "EEG"])
            writer.writerow(["sample_rate_hz", int(self.sample_rate)])
            writer.writerow(["channel_count", int(self.channel_num)])
            writer.writerow(["channels", ",".join(self.channels)])
            writer.writerow(["unit", "uV"])
            writer.writerow(["ads1299_vref_uv", float(self.ads1299_vref_uv)])
            writer.writerow(["ads1299_gain", float(self.ads1299_gain)])
            writer.writerow(["ads1299_leadoff_current_ua", float(self.ads1299_leadoff_current_ua)])
            writer.writerow(["start_time", start_time.isoformat()])
            if patient_info:
                for key, value in patient_info.items():
                    writer.writerow([str(key), str(value)])

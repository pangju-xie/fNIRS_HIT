import logging
from collections import deque

from PyQt5.QtCore import QThread, QTimer, pyqtSignal

from utils import crc
from utils.stats import Commands, Device, SensorTypes, UplinkFrameCodes

logger = logging.getLogger(__name__)


class DeviceProcessManager(QThread):
    signal_device_connected = pyqtSignal(list, object, str)
    signal_device_disconnected = pyqtSignal(list)
    signal_quality_packet = pyqtSignal(int, int, list)
    signal_data_packet = pyqtSignal(int, int, list)
    signal_data_patched = pyqtSignal(int, int, list)
    signal_command_ack = pyqtSignal(object, list, bool)
    signal_battery_updated = pyqtSignal(int)

    def __init__(self, udp_thread):
        super().__init__()
        self.udp_thread = udp_thread
        self.crc_calculator = crc.Crc(0x1021)
        self.devices = {}
        self.command_queue = deque()
        self.active_command = None

        self.cmd_timer = QTimer()
        self.cmd_timer.setSingleShot(True)
        self.cmd_timer.timeout.connect(self._handle_cmd_timeout)

    def add_device(self, device_ip: str, sensor_id: list, sensor_type: SensorTypes) -> bool:
        dev_tuple = tuple(sensor_id)
        if len(self.devices) > 0 and dev_tuple not in self.devices:
            logger.warning("系统忙碌，拒绝设备接入：%s", sensor_id)
            return False

        if dev_tuple not in self.devices:
            self.devices[dev_tuple] = Device(
                ip=device_ip,
                id=sensor_id,
                type=sensor_type,
                port=self.udp_thread.remote_port,
            )
            return True
        return False

    def clear_devices(self):
        self.devices.clear()
        self.command_queue.clear()
        self.active_command = None
        self.cmd_timer.stop()

    def send_command(self, command: Commands, data: list = None, target_device: Device = None):  # type: ignore
        payload = data if data else []
        header = [0xAB, 0xAB]

        if command == Commands.CONNECT:
            sensor_id = [0x00, 0x00, 0x00]
            sensor_type = [SensorTypes.NotInit.value]
            target_ip = self.udp_thread.broadcast_ip
        else:
            if not target_device:
                for dev in self.devices.values():
                    self.send_command(command, payload, dev)
                return True
            sensor_id = target_device.id
            sensor_type = [target_device.type.value]
            target_ip = target_device.ip

        data_len = len(payload)
        len_bytes = [(data_len >> 8) & 0xFF, data_len & 0xFF]
        packet = header + sensor_id + sensor_type + [command.value] + len_bytes + payload
        crc_val = self.crc_calculator.crc16(packet, len(packet))
        packet.extend([crc_val >> 8, crc_val & 0xFF])
        packet_bytes = bytes(packet)

        bypass_cmds = [Commands.DISCONNECT, Commands.BATTERY_QUERY, Commands.DATA_PATCHING]
        if command in bypass_cmds:
            self.udp_thread.send_raw_data(packet_bytes, target_ip, self.udp_thread.remote_port)
        else:
            task = {
                "command": command,
                "packet_bytes": packet_bytes,
                "target_ip": target_ip,
                "sensor_id": sensor_id,
                "retry_count": 0,
            }
            self.command_queue.append(task)
            self._pump_queue()
        return True

    def _pump_queue(self):
        if self.active_command is not None or not self.command_queue:
            return

        self.active_command = self.command_queue.popleft()
        self.udp_thread.send_raw_data(
            self.active_command["packet_bytes"],
            self.active_command["target_ip"],
            self.udp_thread.remote_port,
        )
        self.cmd_timer.start(1000)
        logger.info("发送指令：%s", self.active_command["command"].name)

    def _handle_cmd_timeout(self):
        if not self.active_command:
            return

        if self.active_command["retry_count"] < 3:
            self.active_command["retry_count"] += 1
            logger.warning(
                "指令超时，正在重试：%s（第 %d 次）",
                self.active_command["command"].name,
                self.active_command["retry_count"],
            )
            self.udp_thread.send_raw_data(
                self.active_command["packet_bytes"],
                self.active_command["target_ip"],
                self.udp_thread.remote_port,
            )
            self.cmd_timer.start(1000)
        else:
            failed_cmd = self.active_command["command"]
            sensor_id = self.active_command["sensor_id"]
            logger.error("指令重试后仍失败：%s", failed_cmd.name)
            self.active_command = None
            self.command_queue.clear()
            self.signal_command_ack.emit(failed_cmd, sensor_id, False)

    def acknowledge_command(self, cmd: Commands, sensor_id: list):
        if self.active_command and self.active_command["command"] == cmd:
            self.cmd_timer.stop()
            self.active_command = None
            self._pump_queue()

    def process_raw_packet(self, packet: list, host_ip: str):
        try:
            if len(packet) < 11 or packet[0] != 0xBA or packet[1] != 0xBA:
                logger.warning("帧头无效或数据帧过短：%s", packet)
                return

            sensor_id = packet[2:5]
            sensor_type_val = packet[5]
            command_byte = packet[6]
            data_len = (packet[7] << 8) | packet[8]

            if len(packet) < 11 + data_len:
                logger.warning("数据帧长度不完整：当前=%d，期望>=%d", len(packet), 11 + data_len)
                return

            payload = packet[9 : 9 + data_len]
            crc_recv = (packet[9 + data_len] << 8) | packet[10 + data_len]
            crc_calc = self.crc_calculator.crc16(packet, len(packet) - 2)
            if crc_calc != crc_recv:
                logger.warning("CRC 校验失败，来源：%s", host_ip)
                return

            self._dispatch_frame(command_byte, sensor_id, sensor_type_val, payload, host_ip)
        except Exception as exc:
            logger.error("处理原始数据包失败：%s", exc, exc_info=True)

    def _validate_device(self, is_connect: bool, is_disconnect: bool, sensor_id: list, sensor_type: int) -> bool:
        dev_id_tuple = tuple(sensor_id)
        if is_connect:
            if len(self.devices) > 0 and dev_id_tuple not in self.devices:
                logger.warning("忽略来自非目标设备的连接：%s", sensor_id)
                return False
            return True

        if is_disconnect:
            return True

        if dev_id_tuple not in self.devices:
            logger.warning("丢弃来自未知设备的数据包：%s", sensor_id)
            return False

        registered_type = self.devices[dev_id_tuple].type.value
        if (registered_type & sensor_type) == 0:
            logger.warning("传感器类型不匹配：收到=%s，已注册=%s", sensor_type, registered_type)
            return False
        return True

    def _dispatch_frame(self, command_byte: int, sensor_id: list, sensor_type: int, data: list, ip: str):
        is_connect = command_byte == Commands.CONNECT.value
        is_disconnect = command_byte == Commands.DISCONNECT.value
        if not self._validate_device(is_connect, is_disconnect, sensor_id, sensor_type):
            return

        if self._handle_command_frame(command_byte, sensor_id, sensor_type, data):
            return

        if self._handle_uplink_frame(command_byte, sensor_type, data):
            return

        logger.warning("未知帧类型：0x%02X，来源：%s", command_byte, ip)

    def _handle_command_frame(self, command_byte: int, sensor_id: list, sensor_type: int, data: list) -> bool:
        try:
            cmd = Commands(command_byte)
        except ValueError:
            return False

        dev_id_tuple = tuple(sensor_id)
        is_ack = False
        is_success = False

        if cmd == Commands.CONNECT:
            is_ack = len(data) >= 4
            is_success = is_ack
        elif cmd == Commands.BATTERY_QUERY:
            is_ack = len(data) == 1
            is_success = is_ack
        else:
            is_ack = len(data) == 1
            is_success = is_ack and data[0] == 1

        if is_ack:
            self.acknowledge_command(cmd, sensor_id)
            self.signal_command_ack.emit(cmd, sensor_id, is_success)

        if cmd == Commands.CONNECT and len(data) >= 4:
            device_ip = f"{data[0]}.{data[1]}.{data[2]}.{data[3]}"
            self.signal_device_connected.emit(sensor_id, SensorTypes(sensor_type), device_ip)
            return True

        if cmd == Commands.DISCONNECT and is_success:
            self.devices.pop(dev_id_tuple, None)
            self.signal_device_disconnected.emit(sensor_id)
            return True

        if cmd == Commands.BATTERY_QUERY and len(data) == 1:
            self.signal_battery_updated.emit(data[0])
            return True

        return True

    def _handle_uplink_frame(self, command_byte: int, sensor_type: int, data: list) -> bool:
        try:
            uplink_code = UplinkFrameCodes(command_byte)
        except ValueError:
            return False

        if len(data) < 4:
            logger.warning("上行数据帧过短，无法解析包序号：0x%02X", command_byte)
            return True

        packet_id = (data[-4] << 24) | (data[-3] << 16) | (data[-2] << 8) | data[-1]
        payload = data[:-4]

        if uplink_code == UplinkFrameCodes.QUALITY_DATA:
            self.signal_quality_packet.emit(sensor_type, packet_id, payload)
            return True

        if uplink_code == UplinkFrameCodes.STREAM_DATA:
            self.signal_data_packet.emit(sensor_type, packet_id, payload)
            return True

        if uplink_code == UplinkFrameCodes.PATCHED_DATA:
            self.signal_data_patched.emit(sensor_type, packet_id, payload)
            return True

        return False

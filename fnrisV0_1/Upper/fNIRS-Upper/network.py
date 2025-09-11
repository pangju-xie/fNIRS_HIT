import sys
import socket
import psutil
import ipaddress
import logging
import time
import math
from typing import List, Dict, Optional, Tuple, Callable
from enum import IntEnum
from dataclasses import dataclass
from PyQt5.QtCore import QObject, pyqtSignal, QThread, QTimer
from PyQt5.QtWidgets import QWidget
from PyQt5.QtNetwork import QUdpSocket, QHostAddress, QAbstractSocket
import crc

# Configure logging
logger = logging.getLogger(__name__)

class PacketPosition(IntEnum):
    """Packet structure positions"""
    HEADER1 = 0
    HEADER2 = 1
    SENSOR_ID = 2
    SENSOR_TYPE = 5
    CMD = 6
    DATA_LENGTH = 8
    DATA = 9

class Commands(IntEnum):
    """Protocol command definitions"""
    CONNECT = 0xB0
    DISCONNECT = 0xB1
    START_SAMPLE = 0xC0
    STOP_SAMPLE = 0xC1
    BATTERY_QUERY = 0xC2
    SAMPLE_RATE = 0xC3
    CHANNEL_CONFIG = 0xA0
    DATA_PATCHING = 0xA2

@dataclass
class Device:
    """Device information structure"""
    ip: str
    id: List[int]  # 3-byte sensor ID
    type: int
    
    def __hash__(self):
        return hash((self.ip, tuple(self.id), self.type))
    
    def __eq__(self, other):
        if not isinstance(other, Device):
            return False
        return self.ip == other.ip and self.id == other.id and self.type == other.type

@dataclass
class PendingCommand:
    """Structure for tracking pending commands awaiting acknowledgment"""
    command: Commands
    sensor_id: List[int]
    sensor_type: int
    data: List[int]
    target_ip: str
    retry_count: int = 0
    timestamp: float = 0.0
    callback: Optional[Callable] = None
    
    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()

class NetworkError(Exception):
    """Custom network error class"""
    pass

class UdpPort(QWidget):
    """
    Optimized UDP communication handler for fNIRS sensors with acknowledgment and retransmission
    """
    # Signal: (sensor_id, sensor_type, operation, params)
    onConnectedDevicesChanged = pyqtSignal(list, int, str, list)
    
    # Additional signals for better error handling
    networkError = pyqtSignal(str)
    connectionStatusChanged = pyqtSignal(bool)
    commandAcknowledged = pyqtSignal(int, list, int, bool)  # command, sensor_id, sensor_type, success
    
    def __init__(self, localPort: int = 1227, remotePort: int = 2227):
        super().__init__()
        
        # Network configuration
        self.localPort = localPort
        self.remotePort = remotePort
        
        # Device management
        self.deviceList: List[Device] = []
        self.device_lookup = {}  # For faster device lookups
        
        # Network components
        self.socket: Optional[QUdpSocket] = None
        self.crc = crc.Crc(0x1021)  # CRC-16-CCITT polynomial
        
        # Network info
        self._network_info = None
        self._broadcast_ip = None
        
        # Connection management
        self.is_connected = False
        self.connection_timeout = 5.0  # seconds
        self.max_retries = 3
        
        # Acknowledgment and retransmission settings
        self.max_retransmissions = 5
        self.retransmission_interval = 500  # milliseconds
        self.acknowledgment_timeout = 2000  # milliseconds
        
        # Pending commands tracking
        self.pending_commands: Dict[str, PendingCommand] = {}  # key: sensor_id_tuple + command
        self.retransmission_timer = QTimer()
        self.retransmission_timer.timeout.connect(self._handle_retransmissions)
        self.retransmission_timer.start(self.retransmission_interval)
        
        # Statistics
        self.packets_sent = 0
        self.packets_received = 0
        self.crc_errors = 0
        self.packet_errors = 0
        self.retransmissions = 0
        self.failed_commands = 0
        
        self._initialize_network()
    
    def _initialize_network(self):
        """Initialize network components with error handling"""
        try:
            # Get network information
            self._update_network_info()
            
            # Initialize UDP socket
            self._initialize_socket()
            
            logger.info(f"Network initialized - Local: {self._network_info['ip']}:{self.localPort}, "
                       f"Broadcast: {self._broadcast_ip}:{self.remotePort}")
            
        except Exception as e:
            error_msg = f"Network initialization failed: {e}"
            logger.error(error_msg)
            self.networkError.emit(error_msg)
            raise NetworkError(error_msg)
    
    def _update_network_info(self):
        """Update network interface information"""
        try:
            network_info = self._get_wlan_info()
            if not network_info:
                raise NetworkError("No WLAN interface found")
            
            self._network_info = network_info
            self._broadcast_ip = self._calculate_broadcast_address(
                network_info['ip'], network_info['subnet_mask']
            )
            
        except Exception as e:
            raise NetworkError(f"Failed to get network info: {e}")
    
    def _get_wlan_info(self) -> Optional[Dict[str, str]]:
        """Get WLAN interface information with better error handling"""
        try:
            addrs = psutil.net_if_addrs()
            
            # Try WLAN first, then fallback to other interfaces
            interface_priority = ['WLAN', 'Wi-Fi', 'wlan0', 'eth0', 'en0']
            
            for interface_name in interface_priority:
                if interface_name in addrs:
                    for addr in addrs[interface_name]:
                        if addr.family == socket.AF_INET and not addr.address.startswith('127.'):
                            return {
                                'ip': addr.address,
                                'subnet_mask': addr.netmask,
                                'interface': interface_name
                            }
            
            # If no preferred interface found, use first valid IPv4 address
            for interface, addr_list in addrs.items():
                for addr in addr_list:
                    if (addr.family == socket.AF_INET and 
                        not addr.address.startswith('127.') and
                        not addr.address.startswith('169.254')):  # Exclude link-local
                        return {
                            'ip': addr.address,
                            'subnet_mask': addr.netmask,
                            'interface': interface
                        }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get network interfaces: {e}")
            return None
    
    def _calculate_broadcast_address(self, ip: str, subnet_mask: str) -> str:
        """Calculate broadcast address from IP and subnet mask"""
        try:
            network = ipaddress.IPv4Network(f"{ip}/{subnet_mask}", strict=False)
            return str(network.broadcast_address)
        except Exception as e:
            logger.error(f"Failed to calculate broadcast address: {e}")
            # Fallback to simple broadcast
            return '.'.join(ip.split('.')[:-1] + ['255'])
    
    def _initialize_socket(self):
        """Initialize UDP socket with error handling"""
        try:
            if self.socket:
                self.socket.close()
            
            self.socket = QUdpSocket(self)
            
            # Bind to local address and port
            bind_result = self.socket.bind(
                QHostAddress(self._network_info['ip']), 
                self.localPort
            )
            
            if not bind_result:
                error = self.socket.error()
                raise NetworkError(f"Failed to bind socket: {error}")
            
            # Connect signal
            self.socket.readyRead.connect(self._handle_incoming_datagram)
            self.socket.errorOccurred.connect(self._handle_socket_error)
            
            logger.info(f"UDP socket bound to {self._network_info['ip']}:{self.localPort}")
            
        except Exception as e:
            raise NetworkError(f"Socket initialization failed: {e}")
    
    def _handle_socket_error(self, error: QAbstractSocket.SocketError):
        """Handle socket errors"""
        error_msg = f"Socket error: {self.socket.errorString()}"
        logger.error(error_msg)
        self.networkError.emit(error_msg)
    
    def _create_command_key(self, sensor_id: List[int], command: Commands) -> str:
        """Create unique key for tracking pending commands"""
        return f"{tuple(sensor_id)}_{command.value}"
    
    def _send_command_with_ack(self, command: Commands, sensor_id: List[int], 
                              sensor_type: int, data: List[int] = None, 
                              target_ip: str = None, callback: Callable = None) -> bool:
        """Send command and track for acknowledgment"""
        if data is None:
            data = []
        
        try:
            # Determine target IP
            if target_ip is None:
                if command == Commands.CONNECT:
                    target_ip = self._broadcast_ip
                else:
                    device = self._find_device_by_id(sensor_id)
                    if not device:
                        logger.warning(f"Device not found for sensor ID: {sensor_id}")
                        return False
                    target_ip = device.ip
            
            # Create and send packet
            if self._send_packet(command, sensor_id, sensor_type, data, target_ip):
                # Track command for acknowledgment (except for data packets and broadcasts)
                if (command != Commands.DATA_PATCHING and 
                    command != Commands.CONNECT):
                    
                    cmd_key = self._create_command_key(sensor_id, command)
                    pending_cmd = PendingCommand(
                        command=command,
                        sensor_id=sensor_id,
                        sensor_type=sensor_type,
                        data=data,
                        target_ip=target_ip,
                        callback=callback
                    )
                    self.pending_commands[cmd_key] = pending_cmd
                    
                    logger.debug(f"Command {command.name} sent to {sensor_id}, waiting for acknowledgment")
                
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to send command {command.name}: {e}")
            return False
    
    def _send_packet(self, command: Commands, sensor_id: List[int], 
                    sensor_type: int, data: List[int], target_ip: str) -> bool:
        """Send packet to target IP"""
        try:
            # Build packet
            if command == Commands.CONNECT:
                # Special handling for connection packet
                ip_parts = [int(part) for part in self._network_info['ip'].split('.')]
                datagram = [0xAB, 0xAB, 0, 0, 0, 4, command, 0, 4] + ip_parts
            else:
                # Standard packet format
                data_length = len(data)
                datagram = ([0xAB, 0xAB] + sensor_id + [sensor_type] + 
                           [command, 0, data_length] + data)
            
            # Add CRC
            crc16 = self.crc.crc16(datagram, len(datagram))
            datagram.extend([crc16 >> 8, crc16 & 0xFF])
            
            # Send packet
            bytes_sent = self.socket.writeDatagram(
                bytes(datagram), 
                QHostAddress(target_ip), 
                self.remotePort
            )
            
            if bytes_sent == -1:
                logger.error(f"Failed to send packet to {target_ip}")
                return False
            
            self.packets_sent += 1
            return True
            
        except Exception as e:
            logger.error(f"Error sending packet: {e}")
            return False
    
    def _handle_retransmissions(self):
        """Handle retransmission timer - check for timed out commands"""
        current_time = time.time()
        timeout_threshold = self.acknowledgment_timeout / 1000.0  # Convert to seconds
        
        expired_commands = []
        
        for cmd_key, pending_cmd in self.pending_commands.items():
            if current_time - pending_cmd.timestamp > timeout_threshold:
                expired_commands.append(cmd_key)
        
        for cmd_key in expired_commands:
            pending_cmd = self.pending_commands[cmd_key]
            
            if pending_cmd.retry_count < self.max_retransmissions:
                # Retry command
                pending_cmd.retry_count += 1
                pending_cmd.timestamp = current_time
                self.retransmissions += 1
                
                logger.warning(f"Retransmitting command {pending_cmd.command.name} to "
                             f"{pending_cmd.sensor_id} (attempt {pending_cmd.retry_count}/{self.max_retransmissions})")
                
                self._send_packet(pending_cmd.command, pending_cmd.sensor_id, 
                                pending_cmd.sensor_type, pending_cmd.data, pending_cmd.target_ip)
            else:
                # Max retries exceeded
                self.failed_commands += 1
                del self.pending_commands[cmd_key]
                
                logger.error(f"Command {pending_cmd.command.name} to {pending_cmd.sensor_id} "
                           f"failed after {self.max_retransmissions} retransmissions")
                
                # Emit failure signal
                self.commandAcknowledged.emit(
                    pending_cmd.command, pending_cmd.sensor_id, 
                    pending_cmd.sensor_type, False
                )
                
                # Call failure callback if provided
                if pending_cmd.callback:
                    try:
                        pending_cmd.callback(False, pending_cmd.sensor_id, pending_cmd.command)
                    except Exception as e:
                        logger.error(f"Error in failure callback: {e}")
    
    def _handle_command_acknowledgment(self, command: Commands, sensor_id: List[int], 
                                     sensor_type: int, success: bool):
        """Handle acknowledgment of sent command"""
        cmd_key = self._create_command_key(sensor_id, command)
        
        if cmd_key in self.pending_commands:
            pending_cmd = self.pending_commands.pop(cmd_key)
            
            if success:
                logger.debug(f"Command {command.name} acknowledged by {sensor_id}")
            else:
                logger.warning(f"Command {command.name} rejected by {sensor_id}")
            
            # Emit acknowledgment signal
            self.commandAcknowledged.emit(command, sensor_id, sensor_type, success)
            
            # Call success callback if provided
            if pending_cmd.callback:
                try:
                    pending_cmd.callback(success, sensor_id, command)
                except Exception as e:
                    logger.error(f"Error in acknowledgment callback: {e}")
    
    def sendConnect(self):
        """Send connection broadcast with improved error handling"""
        try:
            # Clear existing devices
            self.deviceList.clear()
            self.device_lookup.clear()
            
            # Send connection broadcast
            success = self._send_command_with_ack(
                Commands.CONNECT, [0, 0, 0], 0, target_ip=self._broadcast_ip
            )
            
            if success:
                self.is_connected = True
                self.connectionStatusChanged.emit(True)
                logger.info(f"Connection broadcast sent to {self._broadcast_ip}:{self.remotePort}")
            else:
                raise NetworkError("Failed to send connection broadcast")
            
        except Exception as e:
            error_msg = f"Connection failed: {e}"
            logger.error(error_msg)
            self.networkError.emit(error_msg)
            raise NetworkError(error_msg)
    
    def sendDisconnect(self):
        """Send disconnection command to all devices"""
        try:
            self._send_empty_data_packet_with_ack(Commands.DISCONNECT)
            self.is_connected = False
            self.connectionStatusChanged.emit(False)
            logger.info("Disconnection commands sent to all devices")
            
        except Exception as e:
            error_msg = f"Disconnection failed: {e}"
            logger.error(error_msg)
            self.networkError.emit(error_msg)
    
    def sendStartSample(self, callback: Callable = None):
        """Start sampling on all connected devices"""
        try:
            self._send_empty_data_packet_with_ack(Commands.START_SAMPLE, callback)
            logger.info("Start sampling commands sent to all devices")
            
        except Exception as e:
            error_msg = f"Start sampling failed: {e}"
            logger.error(error_msg)
            self.networkError.emit(error_msg)
    
    def sendStopSample(self, callback: Callable = None):
        """Stop sampling on all connected devices"""
        try:
            self._send_empty_data_packet_with_ack(Commands.STOP_SAMPLE, callback)
            logger.info("Stop sampling commands sent to all devices")
            
        except Exception as e:
            error_msg = f"Stop sampling failed: {e}"
            logger.error(error_msg)
            self.networkError.emit(error_msg)
    
    def sendBatteryQuery(self, callback: Callable = None):
        """Query battery status from all devices"""
        try:
            self._send_empty_data_packet_with_ack(Commands.BATTERY_QUERY, callback)
            logger.debug("Battery query sent to all devices")
            
        except Exception as e:
            logger.warning(f"Battery query failed: {e}")
    
    def sendSampleRate(self, sensor_id: List[int], sensor_type: int, rate_code: int, 
                      callback: Callable = None):
        """Send sample rate configuration to specific device"""
        try:
            success = self._send_command_with_ack(
                Commands.SAMPLE_RATE, sensor_id, sensor_type, 
                [sensor_type, rate_code], callback=callback
            )
            
            if success:
                logger.info(f"Sample rate {rate_code} sent to device {sensor_id}")
            else:
                logger.error(f"Failed to send sample rate to device {sensor_id}")
            
            return success
            
        except Exception as e:
            error_msg = f"Send sample rate failed: {e}"
            logger.error(error_msg)
            self.networkError.emit(error_msg)
            return False
    
    def sendChannels(self, sensor_id: List[int], sensor_type: int, 
                    lights: int, detectors: int, channels: List[Tuple[int, int]], 
                    callback: Callable = None):
        """Send channel configuration to specific device"""
        try:
            # Calculate channel configuration bytes
            bytes_per_detector = math.ceil(detectors / 8)
            channel_bytes = [0] * (bytes_per_detector * lights)
            
            for light, detector in channels:
                if 1 <= light <= lights and 1 <= detector <= detectors:
                    byte_index = (light - 1) * bytes_per_detector + math.floor((detector - 1) / 8)
                    bit_index = (detector - 1) % 8
                    channel_bytes[byte_index] |= (1 << bit_index)
                else:
                    logger.warning(f"Invalid channel configuration: light={light}, detector={detector}")
            
            data = [sensor_type, lights, detectors] + channel_bytes
            
            success = self._send_command_with_ack(
                Commands.CHANNEL_CONFIG, sensor_id, sensor_type, data, callback=callback
            )
            
            if success:
                logger.info(f"Channel configuration sent to device {sensor_id}: "
                           f"{len(channels)} channels, {lights} lights, {detectors} detectors")
            else:
                logger.error(f"Failed to send channel configuration to device {sensor_id}")
            
            return success
            
        except Exception as e:
            error_msg = f"Send channels failed: {e}"
            logger.error(error_msg)
            self.networkError.emit(error_msg)
            return False
    
    def _send_empty_data_packet_with_ack(self, command: Commands, callback: Callable = None):
        """Send command without data to all connected devices with acknowledgment tracking"""
        if not self.deviceList:
            logger.warning(f"No devices to send command {command.name}")
            return
        
        for device in self.deviceList:
            try:
                self._send_command_with_ack(
                    command, device.id, device.type, [], device.ip, callback
                )
                    
            except Exception as e:
                logger.error(f"Failed to send {command.name} to device {device.id}: {e}")
    
    def _handle_incoming_datagram(self):
        """Handle incoming UDP datagrams with improved error handling"""
        try:
            while self.socket.hasPendingDatagrams():
                datagram_size = self.socket.pendingDatagramSize()
                datagram, host, port = self.socket.readDatagram(datagram_size)
                
                self.packets_received += 1
                self._process_datagram(list(datagram), host.toString(), port)
                
        except Exception as e:
            error_msg = f"Error processing incoming datagram: {e}"
            logger.error(error_msg)
            self.packet_errors += 1
    
    def _process_datagram(self, datagram: List[int], host_ip: str, port: int):
        """Process received datagram with comprehensive validation"""
        try:
            # Validate packet structure
            if not self._validate_packet(datagram):
                return
            
            # Extract packet information
            sensor_id = datagram[PacketPosition.SENSOR_ID:PacketPosition.SENSOR_ID + 3]
            sensor_type = datagram[PacketPosition.SENSOR_TYPE]
            command = datagram[PacketPosition.CMD]
            data_length = datagram[PacketPosition.DATA_LENGTH]
            data = datagram[PacketPosition.DATA:PacketPosition.DATA + data_length]
            
            # Process different command types
            self._handle_command(command, sensor_id, sensor_type, data, host_ip)
            
        except Exception as e:
            logger.error(f"Error processing datagram from {host_ip}: {e}")
            self.packet_errors += 1
    
    def _validate_packet(self, datagram: List[int]) -> bool:
        """Validate packet structure and integrity"""
        # Check minimum packet size
        if len(datagram) < PacketPosition.DATA_LENGTH + 1:
            logger.debug("Packet too short")
            self.packet_errors += 1
            return False
        
        # Check packet headers
        if datagram[PacketPosition.HEADER1] != 0xBA or datagram[PacketPosition.HEADER2] != 0xBA:
            logger.debug("Invalid packet header")
            self.packet_errors += 1
            return False
        
        # Check data length consistency
        data_length = datagram[PacketPosition.DATA_LENGTH]
        expected_length = data_length + 11  # Header + CRC
        if len(datagram) != expected_length:
            logger.debug(f"Data length mismatch: expected {expected_length}, got {len(datagram)}")
            self.packet_errors += 1
            return False
        
        # Validate CRC
        calculated_crc = self.crc.crc16(datagram, len(datagram) - 2)
        received_crc = (datagram[-2] << 8) + datagram[-1]
        if calculated_crc != received_crc:
            logger.debug("CRC validation failed")
            self.crc_errors += 1
            return False
        
        return True
    
    def _handle_command(self, command: int, sensor_id: List[int], sensor_type: int, 
                       data: List[int], host_ip: str):
        """Handle different command types"""
        try:
            if command == Commands.CONNECT:
                self._handle_connect_response(sensor_id, sensor_type, data, host_ip)
            
            elif command == Commands.DISCONNECT:
                success = self._handle_disconnect_response(sensor_id, sensor_type, data)
                self._handle_command_acknowledgment(Commands.DISCONNECT, sensor_id, sensor_type, success)
            
            elif command == Commands.BATTERY_QUERY:
                success = self._handle_battery_response(sensor_id, sensor_type, data)
                self._handle_command_acknowledgment(Commands.BATTERY_QUERY, sensor_id, sensor_type, success)
            
            elif command == Commands.SAMPLE_RATE:
                success = self._handle_sample_rate_response(sensor_id, sensor_type, data)
                self._handle_command_acknowledgment(Commands.SAMPLE_RATE, sensor_id, sensor_type, success)
            
            elif command == Commands.CHANNEL_CONFIG:
                success = self._handle_channel_config_response(sensor_id, sensor_type, data)
                self._handle_command_acknowledgment(Commands.CHANNEL_CONFIG, sensor_id, sensor_type, success)
            
            elif command == Commands.START_SAMPLE:
                success = self._handle_start_sample_response(sensor_id, sensor_type, data)
                self._handle_command_acknowledgment(Commands.START_SAMPLE, sensor_id, sensor_type, success)
            
            elif command == Commands.STOP_SAMPLE:
                success = self._handle_stop_sample_response(sensor_id, sensor_type, data)
                self._handle_command_acknowledgment(Commands.STOP_SAMPLE, sensor_id, sensor_type, success)
            
            elif command == Commands.DATA_PATCHING:
                self._handle_data_packet(sensor_id, sensor_type, data)
            
            else:
                logger.debug(f"Unknown command: 0x{command:02X}")
                
        except Exception as e:
            logger.error(f"Error handling command 0x{command:02X}: {e}")
    
    def _handle_connect_response(self, sensor_id: List[int], sensor_type: int, 
                                data: List[int], host_ip: str):
        """Handle device connection response"""
        if len(data) >= 4:
            device_ip = f"{data[0]}.{data[1]}.{data[2]}.{data[3]}"
            device = Device(ip=device_ip, id=sensor_id, type=sensor_type)
            
            if device not in self.deviceList:
                self.deviceList.append(device)
                self.device_lookup[tuple(sensor_id)] = device
                self.onConnectedDevicesChanged.emit(sensor_id, sensor_type, 'a', [])
                logger.info(f"Device connected: ID={sensor_id}, Type={sensor_type}, IP={device_ip}")
    
    def _handle_disconnect_response(self, sensor_id: List[int], sensor_type: int, data: List[int]) -> bool:
        """Handle device disconnection response"""
        if data and data[0] == 1:
            device = self._find_device_by_id(sensor_id)
            if device:
                self.deviceList.remove(device)
                self.device_lookup.pop(tuple(sensor_id), None)
                self.onConnectedDevicesChanged.emit(sensor_id, sensor_type, 'r', [])
                logger.info(f"Device disconnected: ID={sensor_id}, Type={sensor_type}")
            return True
        return False
    
    def _handle_battery_response(self, sensor_id: List[int], sensor_type: int, data: List[int]) -> bool:
        """Handle battery status response"""
        if data:
            battery_level = data[0]
            self.onConnectedDevicesChanged.emit(sensor_id, sensor_type, 'b', [battery_level])
            logger.debug(f"Battery status - Device {sensor_id}: {battery_level}%")
            return True
        return False
    
    def _handle_sample_rate_response(self, sensor_id: List[int], sensor_type: int, data: List[int]) -> bool:
        """Handle sample rate configuration response"""
        if data and data[0] == 1:
            self.onConnectedDevicesChanged.emit(sensor_id, sensor_type, 's', [])
            logger.info(f"Sample rate configured for device {sensor_id}")
            return True
        return False
    
    def _handle_channel_config_response(self, sensor_id: List[int], sensor_type: int, data: List[int]) -> bool:
        """Handle channel configuration response"""
        if data and data[0] == 1:
            self.onConnectedDevicesChanged.emit(sensor_id, sensor_type, 'c', [])
            logger.info(f"Channel configuration confirmed for device {sensor_id}")
            return True
        return False
    
    def _handle_start_sample_response(self, sensor_id: List[int], sensor_type: int, data: List[int]) -> bool:
        """Handle start sampling response"""
        if data and data[0] == 1:
            logger.info(f"Start sampling confirmed for device {sensor_id}")
            return True
        return False
    
    def _handle_stop_sample_response(self, sensor_id: List[int], sensor_type: int, data: List[int]) -> bool:
        """Handle stop sampling response"""
        if data and data[0] == 1:
            logger.info(f"Stop sampling confirmed for device {sensor_id}")
            return True
        return False
    
    def _handle_data_packet(self, sensor_id: List[int], sensor_type: int, data: List[int]):
        """Handle sensor data packet"""
        self.onConnectedDevicesChanged.emit(sensor_id, sensor_type, 'd', data)
    
    def _find_device_by_id(self, sensor_id: List[int]) -> Optional[Device]:
        """Find device by sensor ID using lookup table"""
        return self.device_lookup.get(tuple(sensor_id))
    
    def get_connected_devices(self) -> List[Device]:
        """Get list of currently connected devices"""
        return self.deviceList.copy()
    
    def get_statistics(self) -> Dict[str, int]:
        """Get communication statistics including retransmission info"""
        return {
            'packets_sent': self.packets_sent,
            'packets_received': self.packets_received,
            'crc_errors': self.crc_errors,
            'packet_errors': self.packet_errors,
            'connected_devices': len(self.deviceList),
            'retransmissions': self.retransmissions,
            'failed_commands': self.failed_commands,
            'pending_commands': len(self.pending_commands)
        }
    
    def reset_statistics(self):
        """Reset communication statistics"""
        self.packets_sent = 0
        self.packets_received = 0
        self.crc_errors = 0
        self.packet_errors = 0
        self.retransmissions = 0
        self.failed_commands = 0
    
    def get_pending_commands(self) -> Dict[str, Dict]:
        """Get information about currently pending commands"""
        pending_info = {}
        current_time = time.time()
        
        for cmd_key, pending_cmd in self.pending_commands.items():
            elapsed_time = current_time - pending_cmd.timestamp
            pending_info[cmd_key] = {
                'command': pending_cmd.command.name,
                'sensor_id': pending_cmd.sensor_id,
                'sensor_type': pending_cmd.sensor_type,
                'retry_count': pending_cmd.retry_count,
                'elapsed_time': elapsed_time,
                'max_retries': self.max_retransmissions
            }
        
        return pending_info
    
    def cancel_pending_command(self, sensor_id: List[int], command: Commands) -> bool:
        """Cancel a pending command to prevent further retransmissions"""
        cmd_key = self._create_command_key(sensor_id, command)
        
        if cmd_key in self.pending_commands:
            pending_cmd = self.pending_commands.pop(cmd_key)
            logger.info(f"Cancelled pending command {command.name} for device {sensor_id}")
            
            # Emit cancellation signal
            self.commandAcknowledged.emit(command, sensor_id, pending_cmd.sensor_type, False)
            return True
        
        return False
    
    def cancel_all_pending_commands(self):
        """Cancel all pending commands"""
        cancelled_count = len(self.pending_commands)
        
        for cmd_key, pending_cmd in self.pending_commands.items():
            self.commandAcknowledged.emit(
                pending_cmd.command, pending_cmd.sensor_id, 
                pending_cmd.sensor_type, False
            )
        
        self.pending_commands.clear()
        logger.info(f"Cancelled {cancelled_count} pending commands")
    
    def set_retransmission_settings(self, max_retransmissions: int = None, 
                                   retransmission_interval: int = None, 
                                   acknowledgment_timeout: int = None):
        """Update retransmission settings"""
        if max_retransmissions is not None:
            self.max_retransmissions = max_retransmissions
            logger.info(f"Max retransmissions set to {max_retransmissions}")
        
        if retransmission_interval is not None:
            self.retransmission_interval = retransmission_interval
            self.retransmission_timer.setInterval(retransmission_interval)
            logger.info(f"Retransmission interval set to {retransmission_interval}ms")
        
        if acknowledgment_timeout is not None:
            self.acknowledgment_timeout = acknowledgment_timeout
            logger.info(f"Acknowledgment timeout set to {acknowledgment_timeout}ms")
    
    def refresh_network(self):
        """Refresh network configuration (useful if network changes)"""
        try:
            old_ip = self._network_info['ip'] if self._network_info else None
            self._update_network_info()
            
            if self._network_info['ip'] != old_ip:
                logger.info(f"Network changed from {old_ip} to {self._network_info['ip']}")
                self._initialize_socket()
            
        except Exception as e:
            error_msg = f"Network refresh failed: {e}"
            logger.error(error_msg)
            self.networkError.emit(error_msg)
    
    def close(self):
        """Clean shutdown of network components"""
        try:
            # Stop retransmission timer
            if self.retransmission_timer.isActive():
                self.retransmission_timer.stop()
            
            # Cancel all pending commands
            self.cancel_all_pending_commands()
            
            # Send disconnect if connected
            if self.is_connected:
                self.sendDisconnect()
            
            # Close socket
            if self.socket:
                self.socket.close()
                self.socket = None
            
            # Clear device lists
            self.deviceList.clear()
            self.device_lookup.clear()
            
            logger.info("Network components closed successfully")
            
        except Exception as e:
            logger.error(f"Error during network shutdown: {e}")
    
    def __del__(self):
        """Destructor to ensure proper cleanup"""
        self.close()
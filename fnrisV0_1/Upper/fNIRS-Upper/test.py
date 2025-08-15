import socket
import crc  # Ensure this module is available or use `crcmod`

def main():
    c = crc.Crc(0x1021)  # CRC-16-CCITT polynomial

    # Create client socket for sending
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)  # Enable broadcast
    dest_addr = ('192.168.3.255', 2227)  # Broadcast address

    try:
        # Prepare data
        b = [0xAB, 0xAB, 0, 0, 0, 4, 0xB0, 0, 4, 192, 168, 3, 24]
        crc16 = c.crc16(b, len(b))
        b.extend([crc16 >> 8, crc16 & 0xFF])  # Append CRC (high byte first)
        print(f"Data with CRC: {[hex(x) for x in b]}")

        # Send data
        client.sendto(bytes(b), dest_addr)
        print(f"Sent data to {dest_addr}")
    
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    main()
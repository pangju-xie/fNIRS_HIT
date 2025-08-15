import socket

def main():
    # Create server socket for receiving
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    local_addr = ('192.168.3.24', 1227)  # Local binding address

    try:
        # Receive response
        server.settimeout(100)
        server.bind(local_addr)
        print(f"Waiting for response on {local_addr}...")

        try:
            data, addr = server.recvfrom(1024)
            print(f"Received data (hex): {data.hex()} from {addr}")
        except socket.timeout:
            print("No response received within timeout.")
    
    except Exception as e:
        print(f"Error: {e}")
    finally:
        server.close()

if __name__ == "__main__":
    main()
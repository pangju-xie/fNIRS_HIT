import numpy as np

class Crc:
    def __init__(self, poly = 0):
        self.crc_table = []
        for i in range(256):
            # reminder = i << 8
            reminder = np.int16(i << 8)
            for j in range(8):
                if reminder & 0x8000:
                    reminder = (reminder << 1) ^ poly
                else:
                    reminder = reminder << 1
            self.crc_table.append(reminder)

    def crc16(self, data, len):
        crc = np.int16(0)
        for i in range(len):
            crc = ((crc << 8) ^ self.crc_table[((crc >> 8) ^ data[i]) % 256]) % 65536
        return crc.astype(int)
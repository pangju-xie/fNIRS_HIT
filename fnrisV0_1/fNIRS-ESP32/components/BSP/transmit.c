#include <stdio.h>
#include <string.h>
#include "transmit.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "uart.h"


#define CRC16_POLY 0x1021

uint8_t sensor_id[3];
uint8_t mac_addr[10];
uint16_t CRC16_Table[256];

static const char* TAG = "TRANSMIT";

SENSOR_TYPE stype;

//初始化CRC16码表
void GenerateCRC16Table(uint16_t poly){
	uint16_t remainder;
	for (int i = 0; i < 256; i++) {
		remainder = i << 8;
		for (int j = 0; j < 8; j++) {
			if (remainder & 0x8000) {
				remainder = (remainder << 1) ^ poly;
			} else {
				remainder = remainder << 1;
			}
		}
		CRC16_Table[i] = remainder;
	}
}

//计算CRC16
uint16_t CRC16Calculate(uint8_t* data, uint16_t len){
	uint16_t crc = 0;
	for (uint16_t i = 0; i < len; i++) {
		uint8_t pos = (uint8_t)((crc >> 8) ^ data[i]);
		crc = (crc << 8) ^ CRC16_Table[pos];
	}
	return crc;
}

void command_init(void){
	GenerateCRC16Table(CRC16_POLY);
	esp_read_mac(mac_addr+2, ESP_MAC_WIFI_STA);
	mac_addr[0] = 0xBB;
	mac_addr[1] = 0xBB;
	ESP_LOGE(TAG,"MAC ADDR: [%02X:%02X:%02X:%02X:%02X:%02X]. ", mac_addr[2], mac_addr[3], mac_addr[4], mac_addr[5], mac_addr[6], mac_addr[7]);
	//uart_tx_task(mac_addr, 8);
}

int DecodeCommand(uint8_t* data, int len){
	//数据帧结构以及crc校验检查
	if(len<FRAME_LEN){
		ESP_LOGE(TAG, "data length wrong.");
		return -1;
	}
	uint16_t header = (uint16_t)(data[0]<<8)|(data[1]<<0);
	stype = (SENSOR_TYPE)data[5];
	T_COMMAND cmd = (T_COMMAND)data[CMD_PLACE];
	uint16_t dlen = (uint16_t)(data[DLEN_PLACE]<<8|data[DLEN_PLACE+1]<<0);
	if((header != DOWNHEADER) && (header != UPHEADER) ){
		ESP_LOGE(TAG, "data header wrong.");
		return -1;
	}
	if(memcmp(data+2, mac_addr+5,3) && cmd != CMD_CONN){
		printf("data sid wrong.\r\n");
		return -1;
	}
	if(len != dlen+FRAME_LEN){
		ESP_LOGE(TAG, "data length loss.");
		return -1;
	}
	uint16_t crc16_read = (uint16_t)(data[len-2]<<8|data[len-1]);
	uint16_t crc16_count = CRC16Calculate(data, len-2);
	if(crc16_read != crc16_count){
		ESP_LOGE(TAG, "crc check error. read: %x, calculate: %x.", crc16_read, crc16_count);
		return -1;
	}
	if(cmd == CMD_CONN || cmd == CMD_DISC){
		return cmd;
	}
	else if(cmd == CMD_START || cmd == CMD_STOP || 
		 cmd == CMD_VBAT ||  cmd == CMD_SPR ||
		  cmd == CMD_CFGC || cmd == CMD_DATA || cmd == CMD_SUPP ){
			ESP_LOGI(TAG, "read command: %02x.", cmd);
			return 0;
		  }
	else{
		ESP_LOGE(TAG, "command error, no this command:%x", cmd);
		return -1;
	}
    return -1;

}

int EncodeCommand(uint8_t* RxBuf, T_COMMAND cmd, uint8_t* data){
	int len = 0;
	RxBuf[0] = 0xBA;
	RxBuf[1] = 0xBA;
	RxBuf[2] = mac_addr[5];
	RxBuf[3] = mac_addr[6];
	RxBuf[4] = mac_addr[7];
	RxBuf[5] = stype;
	RxBuf[CMD_PLACE] = cmd;
	if(cmd == CMD_CONN){
		len = 4;
		RxBuf[DLEN_PLACE] = (uint8_t)((len>>8)&0xff);
		RxBuf[DLEN_PLACE+1] = (uint8_t)(len&0xff);
		RxBuf[DATA_PLACE+0] = data[0];
		RxBuf[DATA_PLACE+1] = data[1];
		RxBuf[DATA_PLACE+2] = data[2];
		RxBuf[DATA_PLACE+3] = data[3];
	}
	else if(cmd == CMD_DISC){
		len = 1;
		RxBuf[DLEN_PLACE] = (uint8_t)((len>>8)&0xff);
		RxBuf[DLEN_PLACE+1] = (uint8_t)(len&0xff);
		RxBuf[DATA_PLACE] = data[0];
	}
	uint16_t crc = CRC16Calculate(RxBuf, FRAME_LEN+len-2);
	*(uint16_t*)(RxBuf+FRAME_LEN+len-2) = ENDIAN_SWAP_16B(crc);
	return FRAME_LEN+len;
}
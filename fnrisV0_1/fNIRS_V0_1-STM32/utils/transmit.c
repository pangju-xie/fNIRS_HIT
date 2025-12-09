#include "transmit.h"
#include "main.h"
#include "usart.h"
#include "spi.h"
#include "string.h"
#include "utils.h"
#include "BAT_ADC.h"
#include "fnirs.h"
#include "sdio.h"
#include "led.h"
#include "fnirs.h"
#include <math.h>

extern DMA_HandleTypeDef hdma_spi2_tx;
extern DMA_HandleTypeDef hdma_usart3_rx;
uint16_t CRC16_Table[256];

uint8_t U_RxBuf[RXBUFSIZE];
UART_RxBuf uart_rx;

uint8_t SensorID[6];
uint8_t ResponseBuf[12] = {0};

volatile uint8_t SendDoneSPI = 1;
volatile uint8_t SendDoneUART = 1;


//spi发送完成中断
void HAL_SPI_TxCpltCallback(SPI_HandleTypeDef *hspi){
	if(hspi->Instance == T_SPI.Instance){
		SendDoneSPI = 1;
		SPI_CS_HIGH;
	}
}

//uart发送完成中断
void HAL_UART_TxCpltCallback(UART_HandleTypeDef *huart){
	if(huart->Instance == T_UART.Instance){
		SendDoneUART = 1;
	}
	else if(huart->Instance == DEBUG_UART.Instance){
		SendDoneDebugUART = 1;
	}
}

//uart接收空闲中断
void HAL_UART_RxIdleCallback(UART_HandleTypeDef *huart){
	if(huart->Instance == T_UART.Instance){
		if(__HAL_UART_GET_FLAG(&T_UART, UART_FLAG_IDLE)){
			// 清除空闲中断标志（否则会一直不断进入中断）
      __HAL_UART_CLEAR_IDLEFLAG(&T_UART);
			HAL_UART_DMAStop(&T_UART);
			uart_rx.index = RXBUFSIZE - __HAL_DMA_GET_COUNTER(&hdma_usart3_rx);
			uart_rx.flag = 1;
			memcpy(uart_rx.buf, U_RxBuf, uart_rx.index);
			memset(U_RxBuf, 0, sizeof(U_RxBuf));
			HAL_UART_Receive_DMA(&T_UART, U_RxBuf, RXBUFSIZE);
		}
	}
}

/*************************************************
 * @description			:	串口dma数据发送
 * @param - data		:	缓存数组
 * @param - len		 	:	数据包长度
 * @param - delay_time 	:	允许最长delay时间
 * @return 				:	
**************************************************/
HAL_StatusTypeDef SPITransmitDMA(uint8_t *data, uint32_t len, uint32_t delay_time){
	//SPI发送数据给esp32的时候，在esp32端会有4个字节覆盖掉原始数据，因此额外发送4个空字节
	HAL_StatusTypeDef res = HAL_ERROR;
	SPI_CS_LOW;
//	res = HAL_SPI_Transmit(&T_SPI, data, len+4, delay_time);
//	SPI_CS_HIGH;
//	DebugPrintf("send %d bytes data to upper by spi.", len);
	while(delay_time--){
		if(SendDoneSPI){
			SPI_CS_LOW;
			SendDoneSPI = 0;
			res = HAL_SPI_Transmit_DMA(&T_SPI, data, len+4);
			//DebugPrintf("spi send %d bytes\r\n", len);
			if(res == HAL_OK){
				return res;
			}
		}
	}
	return res;
}

/*************************************************
 * @description			:	SPI dma数据发送
 * @param - data		:	缓存数组
 * @param - len		 	:	数据包长度
 * @param - delay_time 	:	允许最长delay时间
 * @return 				:	
**************************************************/
HAL_StatusTypeDef UartTransmitDMA(uint8_t *data, uint32_t len, uint32_t delay_time){
	HAL_StatusTypeDef res = HAL_ERROR;
	
	while(delay_time--){
		if(SendDoneUART){
			SendDoneUART = 0;
			res = HAL_UART_Transmit_DMA(&T_UART, data, len);
			DebugPrintf("uart send %d bytes\r\n", len);
			if(res == HAL_OK){
				return res;
			}
		}
	}
	return res;
}

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

//获取ESP32端的mac地址作为设备ID
//数据帧结构为：BB BB ID[0] ID[1] ID[2] ID[3] ID[4] ID[5]
void GetSensorID(void){
	int Delay = 4000;
	while(Delay--){
		if(uart_rx.flag){
			uart_rx.flag = 0;
			if(uart_rx.flag == 8 && uart_rx.buf[0] == 0xBB && uart_rx.buf[1] == 0xBB){
				uart_rx.index = 0;
				memcpy(SensorID, uart_rx.buf+2, 6);
				memset(uart_rx.buf, 0, 8);
				reverseArray(SensorID, 6);
				break;
			}
		}
		HAL_Delay(1);
	}
}

void InitDataBuf(uint8_t *buf, SENSOR_TYPE stype, T_COMMAND cmd, uint16_t len){
	*(uint16_t*)(buf) = ENDIAN_SWAP_16B(UPHEADER);				//应答帧帧头
	memcpy(buf+2, SensorID, 3);													//传感器编号
	buf[5] = stype;																				//设备类型
	buf[CMD_PLACE] = cmd;																	//数据类型
	*(uint16_t*)(buf+DLEN_PLACE) = ENDIAN_SWAP_16B(len);	//应答帧长度
	
	
}

void DataFrameInit(void){
	
	SENSOR_TYPE stype = fNIRS;				//当前设备类型为fNIRS
	GenerateCRC16Table(CRC16_POLY);		
	
	UART_ENABLE(T_UART);
	
	HAL_UART_Receive_DMA(&T_UART, U_RxBuf, RXBUFSIZE);
	
	__HAL_LINKDMA(&T_SPI, hdmatx, hdma_spi2_tx);
	__HAL_DMA_ENABLE_IT(&hdma_spi2_tx, DMA_IT_TC);
	
	//GetSensorID();
	
	//应答帧数据填充
	*(uint16_t*)(ResponseBuf) = ENDIAN_SWAP_16B(UPHEADER);			//应答帧帧头
//	memcpy(ResponseBuf+2, SensorID+3, 3);													//传感器编号
	ResponseBuf[5] = stype;																			//设备类型
	*(uint16_t*)(ResponseBuf+DLEN_PLACE) = ENDIAN_SWAP_16B(1);	//应答帧长度
}

uint8_t SampleRateHandler(uint8_t *data, SENSOR_TYPE stype, uint16_t dlen){
	uint8_t ret = 0;
	uint8_t spr_num = 0;
	for(uint8_t i = 0; i< 4;i++){
		spr_num += GetBit(stype, i);
	}
	if(spr_num*2 != dlen){
		DebugPrintf("sample rate command data length wrong.\r\n");
		return 0;
	}
	for(uint8_t i = 0; i<spr_num;i++){
		SENSOR_TYPE spr_type = (SENSOR_TYPE)data[i*2];
		uint8_t spr = data[i*2+1];
		if((spr_type <=8) && (stype&spr_type)){
			switch(spr_type){
				case EEG:
					ret = 1;
					break;
				case EMG:
					ret = 1;
					break;
				case fNIRS:
					nirs_set_sample_rate(spr);
					ret = 1;
					break;
				case NIRS:
					ret = 1;
					break;
				default:
					break;
			}
		}
	}
	return ret;
}

uint8_t ConfigHandler(uint8_t *data, SENSOR_TYPE stype, uint16_t dlen){
	uint8_t ret = 0;
	uint8_t cfg_num = 0;
	uint8_t baise = 0;
	uint8_t len = 0;
	for(uint8_t i = 0; i< 4;i++){
		cfg_num += GetBit(stype, i);
	}
	for(uint8_t i = 0; i<cfg_num;i++){
		SENSOR_TYPE cfg_type = (SENSOR_TYPE)data[baise];
		if(cfg_type>8 || !(stype& cfg_type)){
			DebugPrintf("config command data type wrong.\r\n");
			return 0;
		}
		if(cfg_type == EEG || cfg_type == EMG){
			uint8_t chn_num = data[baise+1];
			len = 2 + ceil(chn_num/8.0);
			baise = baise + len;
		}
		else if(cfg_type == fNIRS || cfg_type == NIRS){
			uint8_t src_num = data[baise+1];
			uint8_t det_num = data[baise+2];
      uint8_t det_byte = ceil(det_num/8.0);
			len = 3 + src_num * det_byte;
			ret = nirs_config(data+baise+1, det_byte);
			baise = baise + len;
		}
	}
	return ret;
}


void SuppleDataPkg(SENSOR_TYPE stype, uint32_t package){
	switch(stype){
		case(EEG):
			break;
		case(EMG):
			break;
		case(fNIRS):
			sd_read_nirs(package);
			break;
		case(NIRS):
			break;
		default:
			break;
	}
}

void DecodeCommand(uint8_t *data, int len){
	static uint8_t temp =1;
	uint32_t pkg = 0;
	uint8_t respone = 0;
	//数据帧结构以及crc校验检查
	if(len<FRAME_LEN){
		DebugPrintf("data length wrong.\r\n");
		return;
	}
	uint16_t header = (uint16_t)(data[0]<<8)|(data[1]<<0);
	SENSOR_TYPE stype = (SENSOR_TYPE)data[5];
	T_COMMAND cmd = (T_COMMAND)data[CMD_PLACE];
	uint16_t dlen = (uint16_t)(data[DLEN_PLACE]<<8|data[DLEN_PLACE+1]<<0);
	if(header != DOWNHEADER){
		DebugPrintf("data header wrong.\r\n");
		return;
	}
//	if(!memcmp(data+2, SensorID+3,3)){
//		DebugPrintf("daata sid wrong.\r\n");
//		return;
//	}
	
	uint16_t crc16 = (uint16_t)(data[len-2]<<8|data[len-1]);
	if(crc16 != CRC16Calculate(data, len-2)){
		DebugPrintf("crc check error.\r\n");
		//return;
	}
	if(temp ==1){
		temp = 0;
		memcpy(SensorID, data+2, 3);
		memcpy(ResponseBuf+2, data+2, 3);
		fnirs_struct_init();																//初始化fnirs数据结构
	}
	//校验通过
	switch(cmd){
		case CMD_START:
			respone = nirs_start();
			break;
		case CMD_STOP:
			respone = nirs_stop();
			BatteryDetect();					
			break;
		case CMD_VBAT:
			respone = GetBatValue();
			break;
		case CMD_SPR:
			respone = SampleRateHandler(data+DATA_PLACE, stype, dlen);
			break;
		case CMD_CFGC:
			respone = ConfigHandler(data+DATA_PLACE, stype, dlen);
			break;
		case CMD_SUPP:
			memcpy((uint8_t*)&pkg, data+DATA_PLACE+1, 4);
			reverseArray((uint8_t*)&pkg, 4);
			SuppleDataPkg(stype, pkg);
			break;
		default:
			break;
	}
	if(cmd != CMD_SUPP){
		EncodeCommand(cmd, respone);
	}
}

void EncodeCommand(T_COMMAND cmd, uint8_t data){
	ResponseBuf[CMD_PLACE] = cmd;
	ResponseBuf[DATA_PLACE] = data;
	uint16_t crc = CRC16Calculate(ResponseBuf, 10);
	*(uint16_t*)(ResponseBuf+10) = ENDIAN_SWAP_16B(crc);
	
	if(HAL_OK != UartTransmitDMA(ResponseBuf, 12, 1000)){
		DebugPrintf("response data fail.\r\n");
	}
	else{
		SetLED('g');
	}
}
	
	
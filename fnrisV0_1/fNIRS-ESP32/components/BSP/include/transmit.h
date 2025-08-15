#ifndef _TRANSMIT_H
#define _TRANSMIT_H

#ifdef __cplusplus
extern "C"
{
#endif


/* 短整型大小端互换 */
#define ENDIAN_SWAP_16B(x) ((((uint16_t)(x) & 0XFF00) >> 8) | \
							(((uint16_t)(x) & 0X00FF) << 8))

/* 整型大小端互换 */
#define ENDIAN_SWAP_32B(x) ((((uint32_t)(x) & 0XFF000000) >> 24) | \
							(((uint32_t)(x) & 0X00FF0000) >> 8) | \
							(((uint32_t)(x) & 0X0000FF00) << 8) | \
							(((uint32_t)(x) & 0X000000FF) << 24))

							
#define UPHEADER        0xBABA
#define DOWNHEADER      0xABAB

#define CMD_PLACE					6
#define DLEN_PLACE				    7
#define DATA_PLACE				    9
#define FRAME_LEN					11

typedef enum{
	EEG						=	1,
	EMG 					=	2,
	EEG_EMG				    =	3,
	fNIRS					=	4,
	EEG_fNIRS			    =	5,
	EEG_fNIRS_EMG	        =	7,
	NIRS					=	8,
}SENSOR_TYPE;   

typedef enum{
	CMD_CONN 					= 0xB0,
	CMD_DISC 					= 0xB1,
	CMD_START					= 0xC0,
	CMD_STOP 					= 0xC1,
	CMD_VBAT 					= 0xC2,
	CMD_SPR  					= 0xC3,
	CMD_CFGC 					= 0xA0,
	CMD_DATA 					= 0xA1,
	CMD_SUPP 					= 0xA2,
}T_COMMAND;

void command_init(void);
int DecodeCommand(uint8_t* data, int len);
int EncodeCommand(uint8_t* RxBuf, T_COMMAND cmd, uint8_t* data);

#ifdef __cplusplus
}
#endif
#endif 

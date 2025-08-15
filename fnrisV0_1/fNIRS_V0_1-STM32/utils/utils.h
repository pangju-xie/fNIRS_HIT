/**********************************************************************
Copyright ? LIZ MEDICAL TECHNOLOGY Co., Ltd. 2022. All rights reserved.
�ļ���		: utils.h
����	  	: ����Ϊ <458386139@qq.com>
�汾	   	: V1.0
����	   	: ͨ�����
����	   	: ��
��־	   	: ����V1.0 2024/8/14 ����Ϊ����
***********************************************************************/
#ifndef __UTILS_H__
#define __UTILS_H__

#include "main.h"
#include "stdio.h"

#define DEBUG_UART   huart2

typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;

typedef enum{
	ESP_STM_INFO = 0,
	ESP_STM_ERR = 1,
	ESP_STM_DBG = 2,
} STM32_DBG_LEVEL;

#define INFO_PRINT(fmt, ...)	print_redirect_2_esp32(ESP_STM_INFO, fmt, ##__VA_ARGS__)
#define DBG_PRINT(fmt, ...)		print_redirect_2_esp32(ESP_STM_DBG, "(%s, %d) " fmt, __func__, __LINE__, ##__VA_ARGS__)
#define ERR_PRINT(fmt, ...)		print_redirect_2_esp32(ESP_STM_ERR, "error!(%s, %d) " fmt, __func__, __LINE__, ##__VA_ARGS__)

/* ���� */
#define R_SHIFT(val, bit) ((val) << (bit))

/* �����ʹ�С�˻��� */
#define ENDIAN_SWAP_16B(x) ((((uint16_t)(x) & 0XFF00) >> 8) | \
							(((uint16_t)(x) & 0X00FF) << 8))

/* ���ʹ�С�˻��� */
#define ENDIAN_SWAP_32B(x) ((((uint32_t)(x) & 0XFF000000) >> 24) | \
							(((uint32_t)(x) & 0X00FF0000) >> 8) | \
							(((uint32_t)(x) & 0X0000FF00) << 8) | \
							(((uint32_t)(x) & 0X000000FF) << 24))

/*λ����*/

#define GetBit(x, y)  	((x>>y)&0x1)
#define TOGGLE_BIT(reg, bit) ((reg) ^= (1U << (bit)))
#define CHECK_BIT(reg, bit)  ((reg) & (1U << (bit)))

#define SET_BITS(reg, mask)  ((reg) |= (mask))
#define CLEAR_BITS(reg, mask) ((reg) &= ~(mask))
#define MODIFY_BITS(reg, mask, value) ((reg) = ((reg) & ~(mask)) | ((value) & (mask)))

/* */
#define BYTE0(dwTemp)       ( *( (char *)(&dwTemp)		) )
#define BYTE1(dwTemp)       ( *( (char *)(&dwTemp) + 1) )
#define BYTE2(dwTemp)       ( *( (char *)(&dwTemp) + 2) )
#define BYTE3(dwTemp)       ( *( (char *)(&dwTemp) + 3) )

/*��ȡ���뺯��*/
uint32_t getUs(void);
void user_delay_us(uint32_t micros);
void Delay_us(uint32_t udelay);

extern volatile uint8_t SendDoneDebugUART;

/*************************************************
 * @description			:	8λcrc���������
 * @param - data		:	���ݵ�ַ
 * @param - len			:	���ݳ���
 * @return 				:	8λcrc������
**************************************************/
uint8_t crc_8bit(uint8_t data[], uint8_t len);
void GenerateTable(uint8_t poly);

uint8_t crc_8bit_fast(uint8_t data[], int len);

//��ת���飬�����ڴ�С��ת����
void reverseArray(uint8_t *data, int size);
/*************************************************
 * @description			:	��Ϣ�ض���esp32����
 * @param - level		:	���Դ�ӡ�ȼ�
 * @param - format		:	��ӡ��ʽ
 * @return 				:	��
**************************************************/
void DebugPrintf(char * format, ...);

int fputc(int ch, FILE *f);
#endif /* __UTILS_H__ */


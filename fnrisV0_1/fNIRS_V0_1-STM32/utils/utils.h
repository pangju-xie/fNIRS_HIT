/**********************************************************************
Copyright ? LIZ MEDICAL TECHNOLOGY Co., Ltd. 2022. All rights reserved.
文件名		: utils.h
作者	  	: 刘有为 <458386139@qq.com>
版本	   	: V1.0
描述	   	: 通用组件
其他	   	: 无
日志	   	: 初版V1.0 2024/8/14 刘有为创建
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

/* 右移 */
#define R_SHIFT(val, bit) ((val) << (bit))

/* 短整型大小端互换 */
#define ENDIAN_SWAP_16B(x) ((((uint16_t)(x) & 0XFF00) >> 8) | \
							(((uint16_t)(x) & 0X00FF) << 8))

/* 整型大小端互换 */
#define ENDIAN_SWAP_32B(x) ((((uint32_t)(x) & 0XFF000000) >> 24) | \
							(((uint32_t)(x) & 0X00FF0000) >> 8) | \
							(((uint32_t)(x) & 0X0000FF00) << 8) | \
							(((uint32_t)(x) & 0X000000FF) << 24))

/*位操作*/

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

/*获取毫秒函数*/
uint32_t getUs(void);
void user_delay_us(uint32_t micros);
void Delay_us(uint32_t udelay);

extern volatile uint8_t SendDoneDebugUART;

/*************************************************
 * @description			:	8位crc检验码计算
 * @param - data		:	数据地址
 * @param - len			:	数据长度
 * @return 				:	8位crc检验码
**************************************************/
uint8_t crc_8bit(uint8_t data[], uint8_t len);
void GenerateTable(uint8_t poly);

uint8_t crc_8bit_fast(uint8_t data[], int len);

//反转数组，可用于大小端转换。
void reverseArray(uint8_t *data, int size);
/*************************************************
 * @description			:	信息重定向到esp32串口
 * @param - level		:	调试打印等级
 * @param - format		:	打印格式
 * @return 				:	无
**************************************************/
void DebugPrintf(char * format, ...);

int fputc(int ch, FILE *f);
#endif /* __UTILS_H__ */


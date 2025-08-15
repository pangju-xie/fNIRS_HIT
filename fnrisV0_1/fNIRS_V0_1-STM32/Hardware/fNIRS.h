#ifndef __FNIRS__H
#define __FNIRS__H

#include "main.h"
#include "stdio.h"
#include "stdint.h"
#include "CSNP32.h"

#define LEN_ONE_DOT					(3)
#define LEN_ONE_SOURCE			(LEN_ONE_DOT*2)

#define fNIRS_TIM						htim9

#define FNIRS_PERIOD				1

typedef enum{
	INIT  = 0,								//初始化
	READY = 1,								//初始化完成
	START = 2,								//开始
	STOP  = 3,								//结束
}FNIRS_STATE;

typedef struct{
	uint8_t source;						//光源数
	uint8_t detect;						//探测器数
	uint16_t config[20];			//光源-探测器配置
	uint8_t open[20];					//每个光源所开启的探测器数
	uint8_t open_count[20];		//对上面的累加
}FNIRS_CONFIG;

typedef struct{
	uint8_t readbuf[50];							//光电数据暂存数组
}FNIRS_READ_BUF;

typedef struct{
	uint8_t idx;											
	FNIRS_READ_BUF buf[2];						//red和ir光电数据暂存数组
}FNIRS_ADS_BUF;

typedef struct{
	uint8_t chn_data[1800];						//fnirs数据保存数组
}FNIRS_DATA_STRUCT;

typedef struct{
	uint8_t idx;											//缓存数组选择
	uint32_t period; 									//发送批次
	int datalen;											//数据帧长度
	int length;												//发送数组长度
  uint8_t *SaveAddr;                //读取数据时保存地址
	FNIRS_DATA_STRUCT send_buf[2];		//双缓存发送数组
	FNIRS_ADS_BUF buffer;							//双缓存暂存数组
	SD_CARD_STRUCT sd_buff;
}FNIRS_DATA_BUF;

typedef struct{
	FNIRS_STATE state;								//fNIRS状态
	uint8_t sample_rate;							//fNIRS采样率
	FNIRS_CONFIG config; 							//fNIRS网络结构配置
	FNIRS_DATA_BUF databuf;						//fNIRS双缓存数组
	uint32_t tim_count;								//TIM计数器
}FNIRS_STRUCT;


void fnirs_struct_init(void);

/*************************************************
 * @description			:	脑氧采集功能初始化
 * @param 				:	无
 * @return 				:	无
**************************************************/
void nirs_init(void);

/*************************************************
 * @description			:	脑氧设置采样率
 * @param 			 spr:	采样率
 * @return 				:	无
**************************************************/
uint8_t nirs_set_sample_rate(uint8_t spr);

/*************************************************
 * @description			:	脑氧配置网络结构
 * @param 			 data:	配置结构数组
 * @return 				:	无
**************************************************/
uint8_t nirs_config(uint8_t* data, uint8_t len);

/*************************************************
 * @description			:	脑氧采集功能开启
 * @param 				:	无
 * @return 				:	无
**************************************************/
uint8_t nirs_start(void);

/*************************************************
 * @description			:	脑氧采集功能关闭
 * @param 				:	无
 * @return 				:	无
**************************************************/
uint8_t nirs_stop(void);

/*************************************************
 * @description			:	获取脑氧功能状态
 * @param - 			:	无
 * @return 				:	无
**************************************************/
uint8_t nirs_get_state(void);
uint16_t nirs_get_len(void);
/*************************************************
 * @description			:	定时处理函数
 * @param 				:	无
 * @return 				:	无
**************************************************/
void nirs_timer_handle(void);

/*************************************************
 * @description			:	脑氧数据采集
 * @param - gpio_pin	:	引脚号
 * @return 				:	无
**************************************************/
void nirs_data_collect(uint16_t gpio_pin);

void sd_read_nirs(uint32_t pkg);

#endif


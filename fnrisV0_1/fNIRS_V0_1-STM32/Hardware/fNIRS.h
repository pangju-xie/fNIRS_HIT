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
	INIT  = 0,								//��ʼ��
	READY = 1,								//��ʼ�����
	START = 2,								//��ʼ
	STOP  = 3,								//����
}FNIRS_STATE;

typedef struct{
	uint8_t source;						//��Դ��
	uint8_t detect;						//̽������
	uint16_t config[20];			//��Դ-̽��������
	uint8_t open[20];					//ÿ����Դ��������̽������
	uint8_t open_count[20];		//��������ۼ�
}FNIRS_CONFIG;

typedef struct{
	uint8_t readbuf[50];							//��������ݴ�����
}FNIRS_READ_BUF;

typedef struct{
	uint8_t idx;											
	FNIRS_READ_BUF buf[2];						//red��ir��������ݴ�����
}FNIRS_ADS_BUF;

typedef struct{
	uint8_t chn_data[1800];						//fnirs���ݱ�������
}FNIRS_DATA_STRUCT;

typedef struct{
	uint8_t idx;											//��������ѡ��
	uint32_t period; 									//��������
	int datalen;											//����֡����
	int length;												//�������鳤��
  uint8_t *SaveAddr;                //��ȡ����ʱ�����ַ
	FNIRS_DATA_STRUCT send_buf[2];		//˫���淢������
	FNIRS_ADS_BUF buffer;							//˫�����ݴ�����
	SD_CARD_STRUCT sd_buff;
}FNIRS_DATA_BUF;

typedef struct{
	FNIRS_STATE state;								//fNIRS״̬
	uint8_t sample_rate;							//fNIRS������
	FNIRS_CONFIG config; 							//fNIRS����ṹ����
	FNIRS_DATA_BUF databuf;						//fNIRS˫��������
	uint32_t tim_count;								//TIM������
}FNIRS_STRUCT;


void fnirs_struct_init(void);

/*************************************************
 * @description			:	�����ɼ����ܳ�ʼ��
 * @param 				:	��
 * @return 				:	��
**************************************************/
void nirs_init(void);

/*************************************************
 * @description			:	�������ò�����
 * @param 			 spr:	������
 * @return 				:	��
**************************************************/
uint8_t nirs_set_sample_rate(uint8_t spr);

/*************************************************
 * @description			:	������������ṹ
 * @param 			 data:	���ýṹ����
 * @return 				:	��
**************************************************/
uint8_t nirs_config(uint8_t* data, uint8_t len);

/*************************************************
 * @description			:	�����ɼ����ܿ���
 * @param 				:	��
 * @return 				:	��
**************************************************/
uint8_t nirs_start(void);

/*************************************************
 * @description			:	�����ɼ����ܹر�
 * @param 				:	��
 * @return 				:	��
**************************************************/
uint8_t nirs_stop(void);

/*************************************************
 * @description			:	��ȡ��������״̬
 * @param - 			:	��
 * @return 				:	��
**************************************************/
uint8_t nirs_get_state(void);
uint16_t nirs_get_len(void);
/*************************************************
 * @description			:	��ʱ������
 * @param 				:	��
 * @return 				:	��
**************************************************/
void nirs_timer_handle(void);

/*************************************************
 * @description			:	�������ݲɼ�
 * @param - gpio_pin	:	���ź�
 * @return 				:	��
**************************************************/
void nirs_data_collect(uint16_t gpio_pin);

void sd_read_nirs(uint32_t pkg);

#endif


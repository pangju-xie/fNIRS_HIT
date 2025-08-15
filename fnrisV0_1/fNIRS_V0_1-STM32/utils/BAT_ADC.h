/**********************************************************************
Copyright ? LIZ MEDICAL TECHNOLOGY Co., Ltd. 2022. All rights reserved.
�ļ���		: bat_adc.h
����	  	: л����<823767544@qq.com>
�汾	   	: V1.0
����	   	: �������ͷ�ļ�
����	   	: ��
��־	   	: ����V1.0 2024/8/10 л���Ĵ���
***********************************************************************/
#ifndef __BAT_ADC__H
#define __BAT_ADC__H

#ifdef __cplusplus
extern "C" {
#endif

#include "main.h"
#include <stdio.h>
#include <adc.h>
	
#define BATREF					6600
#define ADC_BIT					4096

#define	BAT100					4200	
#define	BAT90					4080
#define	BAT80					4000
#define	BAT70					3930
#define	BAT60					3870
#define	BAT50					3820
#define	BAT40					3790
#define	BAT30					3770
#define	BAT20					3730
#define BAT10					3680
#define BAT0					2500

extern uint8_t IFSendADC;
/*************************************************
 * @description			:	������
 * @param 				:	
 * @return 				:	
**************************************************/
void BatteryDetect(void);

/*************************************************
 * @description			:	��������ѹת��Ϊ�����ٷֱ�
 * @param - bat_value	:	��ص�ѹ
 * @param - sendbool	:	�Ƿ�������
 * @return 				:	
**************************************************/
uint8_t SwitchBat2Pct(uint16_t bat_value);
void bat_init(void);
uint16_t get_bat_adc_value(void);
uint8_t GetBatValue(void);
#ifdef __cplusplus
}
#endif

#endif /* __MAIN_H */



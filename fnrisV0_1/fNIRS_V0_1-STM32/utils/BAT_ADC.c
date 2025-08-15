/**********************************************************************
Copyright ? LIZ MEDICAL TECHNOLOGY Co., Ltd. 2022. All rights reserved.
�ļ���		: bat_adc.h
����	  	: л����<823767544@qq.com>
�汾	   	: V1.0
����	   	: �������ͷ�ļ�
����	   	: ��
��־	   	: ����V1.0 2024/8/10 л���Ĵ���
***********************************************************************/
#include "BAT_ADC.h"
#include <stdio.h>
#include <usart.h>
#include "utils.h"
#include "main.h"
#include "led.h"

uint16_t bat_thershold[11] = {BAT0, BAT10, BAT20, BAT30, BAT40, BAT50, BAT60, BAT70, BAT80, BAT90, BAT100};
uint16_t ADC_value = 0;
uint16_t Battery_value = BAT100;
uint8_t PBAT = 0;
/*************************************************
 * @description			:	������
 * @param 				:	
 * @return 				:	
**************************************************/
void BatteryDetect(void){
	

	HAL_ADC_Start(&hadc1);		//����adc
	HAL_ADC_PollForConversion(&hadc1, 100);		//�ȴ�ת�����	
	if(HAL_IS_BIT_SET(HAL_ADC_GetState(&hadc1), HAL_ADC_STATE_REG_EOC))
	{
		ADC_value = HAL_ADC_GetValue(&hadc1);
		Battery_value = ADC_value*BATREF/ADC_BIT;
	}
	PBAT = SwitchBat2Pct(Battery_value);
	DebugPrintf("current battery value: %d.\r\n", PBAT);
	
	if(Battery_value >= BAT70){
		SetLED('g');
	}
	else if(Battery_value >= BAT20){
		SetLED('y');
	}
	else{
		SetLED('r');
	}
}


 /*************************************************
 * @description			:	����У��ֵ�������ۼӷ�����
 * @param - buf			:	���ͻ�������
 * @param - len			:	���鳤��
 * @return - sum		:	У����
**************************************************/
uint8_t CountSum(uint8_t *buf, uint8_t len){
	uint8_t sum = 0;
	for(uint8_t i = 0; i<len;i++){
		sum += buf[i];
	}
	return sum;
}

/*************************************************
 * @description			:	��������ѹת��Ϊ�����ٷֱ�
 * @param - bat_value	:	��ص�ѹ
 * @param - sendbool	:	�Ƿ�������
 * @return 				:	
**************************************************/
uint8_t SwitchBat2Pct(uint16_t bat_value){
	for(int i = 10; i>= 0; i--){
		if(bat_value >= bat_thershold[i]){
			return i*10;
			//break;
		}
	}
	return 0;
}
/*************************************************
 * @description			    :	��ȡ��ѹ�ٷֱ�
 * @param 							:
 * @return - bat_value	:	��ص�ѹ
**************************************************/
uint8_t GetBatValue(void){
	return PBAT;
}







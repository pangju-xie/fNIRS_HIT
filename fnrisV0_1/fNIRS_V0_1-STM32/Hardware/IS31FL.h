/**********************************************************************
Copyright : Xie Fawen. 2025. All rights reserved.
�ļ���			: IS31FL.h
����	  	: л����<823767544@qq.com>
�汾	   	: V1.0
����	   	: IS31FL���������оƬͷ�ļ�
����	   	: ��
��־	   	: ����V1.0 2025/2/27 л���Ĵ���
***********************************************************************/
#ifndef __IS31FL_H
#define __IS31FL_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>

#define IS31FL_I2C								(hi2c2)		

#define IS31FL_ADDR								(0x78)								//оƬ�ӻ���ַ��ֻ֧��д����0x7A 0x7C 0X7E
#define LED_CHN_NUM								(36)									//����36·�Ĵ���

#define REGADDR_SHUTDOWN					(0x00)								//�ػ�ָ��Ĵ���
#define REGADDR_PWN_START					(0x01)								//PWM����ָ��Ĵ���
#define REGADDR_PWM_UPDATE				(0x25)								//����PWMָ��ֵ��LED����ָ��ֵ�ļĴ�������Ҫͨ����üĴ���д���ַ���и���
#define REGADDR_LED_CTRL					(0x26)								//LED����ָ��Ĵ���
#define REGADDR_LED_G_CTRL				(0x4A)								//LEDȫ�ֿ���ָ��Ĵ���
#define REGADDR_FOUT_SET					(0x4B)								//�������Ƶ�ʼĴ���
#define REGADDR_RESET							(0x4F)								//����ָ��Ĵ���

//reg0���ػ�����ָ��
#define SSD_SD										(0x00)								//�������оƬ�ػ�
#define SSD_NRM										(0x01)								//оƬ��������ģʽ

//reg1-reg36:PWM����ָ��
/*ָ��ֵ��Χ��0-255�����ڵ���LED��ǿ��36ͨ��LED��������*/

//reg37:PWM����ָ��
/*PWM����ָ���LED����ָ���ֵ��������ʱ�Ĵ����ϣ���Ҫͨ��PWM����ָ����и���
��ָ�Χ����1-36��38-37����PWM����ָ���LED����ָ��ļĴ�����ַ*/

//reg38-73:LED����ָ��
#define CUR_I_DIV_1								(0x00<<1)							//�������Ϊ������/1
#define CUR_I_DIV_2								(0x01<<1)							//�������Ϊ������/2
#define CUR_I_DIV_3								(0x02<<1)							//�������Ϊ������/3
#define CUR_I_DIV_4								(0x033<<1)							//�������Ϊ������/4

#define LED_STATE_OFF							(0x00)							//�ر�ͨ��LED
#define LED_STATE_ON							(0x01)							//����ͨ��LED

//reg74:LEDȫ�ֿ���
#define LEG_G_NRM									(0x00)								//����ͨ����������
#define LEG_G_SD 									(0x01)								//����ͨ��ȫ�ر�

//reg75:LED���Ƶ�ʿ���
#define FOUT_3K										(0x00)								//LED���Ƶ��Ϊ3kHz
#define FOUT_22K									(0x01)								//LED���Ƶ��Ϊ22kHz


#define DISABLE_IS31FL()					HAL_GPIO_WritePin(SDB_GPIO_Port, SDB_Pin,GPIO_PIN_RESET)
#define ENABLE_IS31FL()						HAL_GPIO_WritePin(SDB_GPIO_Port, SDB_Pin,GPIO_PIN_SET)
/********************************************
	* @description		:IS31FLд����ֽ�
	* @param	 REGAddr:д��Ĵ�����ַ
	* @param	 Val    :д��Ĵ�������
	* @param	 len    :д��Ĵ������鳤��
	* @return					:
********************************************/
void LEDWriteMultiData(uint8_t REGAddr, uint8_t* Val, uint8_t len);


void SetLED_ALL(uint8_t on);										//��������led����
void SetPWM_ALL(uint8_t pwm);										//�������й�ǿ�ȣ�Ϊ0-255
void SetIR(uint8_t chn, uint8_t on);						//����IR��
void SetRED(uint8_t chn, uint8_t on);						//����RED��
void SwitchSameLED(uint8_t chn);								//�л�RED/IR��
void SwitchDiffLED(uint8_t chn1, uint8_t chn2);	//�л�IR/RED��
void SwitchLEDLight(void);


/********************************************
	* @description		:IS31FL��ʼ��
	* @param					:
	* @return					:
********************************************/
void LED_Init(void);

/********************************************
	* @description		:IS31FL�ػ�ָ��
	* @param			 val:�ػ�->SSD_SD, ��������->SSD_NRM
	* @return					:
********************************************/
void LED_ShutDown(uint8_t val);

/********************************************
	* @description		:IS31FL��λָ��
	* @param					:
	* @return					:
********************************************/
void LED_Reset(void);

/********************************************
	* @description		:IS31FLȫ�ֿ���LEDָ��
	* @param			 val:ȫ��->LEG_G_SD, ��������->LEG_G_NRM
	* @return					:
********************************************/
void LED_GControl(uint8_t val);

/********************************************
	* @description		:IS31FL�Ĵ�������ָ��
	* @param			 		:
	* @return					:
********************************************/
void LED_Update(void);

/********************************************
	* @description		:IS31FL����PWMָ��
	* @param			 chn:���õ�ͨ����->0-35
	* @param			 val:����PWMֵ->0-255
	* @return					:
********************************************/
void LED_PWM_Config(uint8_t chn, uint8_t val);

/********************************************
	* @description		:IS31FL����LEDָ��
	* @param			 chn:���õ�ͨ����->0-35
	* @param			 val:���õ�����С-> 0-3
	* @param		 state:���õ�LED״̬���رգ�LED_STATE_OFF��������LED_STATE_ON
	* @return					:
********************************************/
void LED_Control(uint8_t chn, uint8_t cur, uint8_t state);

/********************************************
	* @description		:IS31FL�������Ƶ��ָ��
	* @param			 val:FOUT_3K /  FOUT_22K
	* @return					:
********************************************/
void LED_OFS(uint8_t val);

/********************************************
	* @description		:IS31FL��������
	* @param					:
	* @return					:
********************************************/
void LED_Test(void);


#ifdef __cplusplus
}
#endif

#endif

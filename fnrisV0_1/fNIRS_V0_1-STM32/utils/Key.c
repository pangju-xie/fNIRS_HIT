/**********************************************************************
Copyright ? LIZ MEDICAL TECHNOLOGY Co., Ltd. 2022. All rights reserved.
�ļ���		: key.h
����	  	: л����<823767544@qq.com>
�汾	   	: V1.0
����	   	: ��������ͷ�ļ�
����	   	: ��
��־	   	: ����V1.0 2024/8/10 л���Ĵ���
***********************************************************************/
#include "Key.h"
#include "led.h"
#include "stdio.h"
#include "utils.h"

uint8_t key_return = NON_KEY;

#define LONG_PRESS_CNT 100
#define TWICE_PRESS_CNT 20

/**
  * @brief  KEY_Scan();// �������
  * @note   ������⣬���ص�����˫��������
  * @param  ��
  * @retval ��
	PS:key_return�����ⲿȫ�ֱ��������ڽ��ܷ�����Ϣ
  */	
uint8_t KEY_Scan(void)
{
	//����ϵͳ
	static uint8_t  Click_Buf = FALSE;  	//��һ�ε����־����������˫���ĵ�һ�ΰ��º͵ڶ��ΰ���
	static uint8_t  KEY_flag= FALSE;		//��־�����жϱ�־λ�������ڷ���������ͳһ����
	static uint8_t  Click   = FALSE;		//�����жϱ�־λ
	static uint8_t  Long_Press = FALSE; 	//�����жϱ�־λ
	static uint8_t  Double_Click  = FALSE;	//˫���жϱ�־λ
	 
	static uint8_t key_state = KEY_Up;
	
	//��ʱϵͳ
	//��ʱ��10ms����һ�κ���
	static uint8_t  Long_Cnt = LONG_PRESS_CNT;//������ʱʱ��1s
	static uint8_t  Twice_Cnt = TWICE_PRESS_CNT;//˫�������ʱʱ��200ms
	Long_Cnt--;
	Twice_Cnt--;
	
	//״̬ϵͳ
	switch(key_state)
	{
		/*״̬1������״̬���������Ͱ��������˫����*/
		case KEY_Up:
		{	
			if(ReadKey() == 0){
				key_state = KEY_Down;//�л���״̬3
				Long_Cnt = LONG_PRESS_CNT;//������ʱ��ʼ
			}
			else{
				//�ж��Ƿ�Ϊ��������״̬
				if(Click_Buf == TRUE){
					//����ʱ�䳬��200ms,˫���ж�ʱ��ʧЧ����һ����Ϊ������ֱ���ж�Ϊ����
					if(Twice_Cnt<=0){
						KEY_flag = TRUE;
						Click = TRUE;
					}
				}
			}
			break;
		}
    /*״̬3���������µ�������־����״̬*/
		case KEY_Down:
    {
      if(ReadKey() == 1){
        key_state = KEY_Up;//�л���״̬4
        //���ǳ������������ж��ǲ���˫������
        if(Long_Press == FALSE){
          //˫�����
          //ǰ���Ѿ�����һ�Σ���ξ��ж�Ϊ˫������
          if(Click_Buf == TRUE){
			KEY_flag = TRUE;
			Double_Click  = TRUE;
          }
          else{
            //���ǵ�����˫���ĵ�һ�ε������־λ��1
            Click_Buf = TRUE;
            //˫����ʱ����ʼ��ʱ
			Twice_Cnt = TWICE_PRESS_CNT;
          } 
        }
      }
      else{
        //������⣨һֱ�ڰ��£���һ�ε��𲻻ᴥ����
        if(Long_Press == FALSE&&Click_Buf == FALSE){
			//1sʱ�䵽���ж�Ϊ����
			if(Long_Cnt<=0){
				key_state = KEY_wait;//�л���״̬4
				KEY_flag = TRUE;
				Long_Press = TRUE;
			}
        }
      }  
      break;  
    }
    
    /*״̬4����־�������ȴ���������״̬*/
    case KEY_wait:
    {
      if(ReadKey() == 1)
        key_state = KEY_Up;//���һ�ΰ�������,�л���״̬1
      break;
    }
		
    default:
      key_state = KEY_Up;//Ĭ��������л���״̬1
      break;
  }
	
	//��־�������������
	//PS:key_return�����ⲿȫ�ֱ��������ڽ��ܷ�����Ϣ
	if(KEY_flag == TRUE)
	{
	//	static uint16_t HZ = 1000;
		//��������������ģʽ
		if(Click == TRUE){
			key_return = SHORT_KEY;
			/*single click function start*/
			DebugPrintf("single click.\r\n");
			/*single click function end*/
		}
		//�����������ػ�
		else if(Long_Press == TRUE){
			key_return = LONG_KEY;
			/*long time click function start*/
			DebugPrintf("long time click, switch off.\r\n");
			SetLED('o');
			SetKey(LEDOFF);
			/*long time click function end*/
			
		}
		//˫������������ģʽ
		else if(Double_Click == TRUE){
			key_return = DOUBLE_CLICK;
			/*double click function start*/
			DebugPrintf("double click.");
			/*double click function end*/
		}
		//����״̬λ���㣬Ϊ��һ�ΰ���׼��
		KEY_flag= FALSE;
		Click_Buf = FALSE;
		Click = FALSE;
		Long_Press = FALSE;
		Double_Click  = FALSE;
	}
	return key_state==KEY_Up?0:1;
}


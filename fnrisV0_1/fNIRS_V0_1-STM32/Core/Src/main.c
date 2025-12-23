/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : Main program body
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2025 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */
/* USER CODE END Header */
/* Includes ------------------------------------------------------------------*/
#include "main.h"
#include "adc.h"
#include "dma.h"
#include "sdio.h"
#include "spi.h"
#include "tim.h"
#include "usart.h"
#include "gpio.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#include "led.h"
#include "utils.h"
#include "key.h"
#include "bat_adc.h"
#include "fnirs.h"
#include "transmit.h"
#include "CSNP32.h"
#include "tlc5940.h"
#include "ads1258.h"
/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */

/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/

/* USER CODE BEGIN PV */

/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
/* USER CODE BEGIN PFP */

/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */
uint8_t g_timer_ready_flag = 0;

void HAL_TIM_PeriodElapsedCallback(TIM_HandleTypeDef *htim)
{
	static uint32_t __cnt = 0;
	if(htim == &htim6)
		{	
			uint8_t key_state = 0;
			key_state = KEY_Scan();		//按键检测
			__cnt++;
			if(key_state==0 && __cnt >1000){			
				get_battery_status();		//10S检测一次电量
				//HAL_UART_Transmit(&huart2, txd, 30, 100);
				__cnt = 0;
			}
		}
		
	if(htim == g_tlc.tlctim)
	{
		g_timer_ready_flag = 1;
	}
  if(htim == &htim2){
    SETBLANK(GPIO_ON);
    SETBLANK(GPIO_OFF);
  }

}
void HAL_TIM_IC_CaptureCallback(TIM_HandleTypeDef *htim)
{
  if(htim == g_tlc.tlctim)
  {
    // 判断边沿类型
    if(g_tlc.tlctim_polarity == TIM_ICPOLARITY_RISING)
    {
      g_timer_ready_flag = 1;
      // 切换为下降沿检测
      __HAL_TIM_SET_CAPTUREPOLARITY(g_tlc.tlctim, TIM_CHANNEL_2, TIM_ICPOLARITY_FALLING);
      g_tlc.tlctim_polarity = TIM_INPUTCHANNELPOLARITY_FALLING;
    }
    else
    {
      // 下降沿处理
      g_timer_ready_flag = 2;
      // 切换为上升沿检测
      __HAL_TIM_SET_CAPTUREPOLARITY(g_tlc.tlctim, TIM_CHANNEL_2, TIM_ICPOLARITY_RISING);
      g_tlc.tlctim_polarity = TIM_INPUTCHANNELPOLARITY_RISING;
    }
  }
}
/* USER CODE END 0 */

/**
  * @brief  The application entry point.
  * @retval int
  */
int main(void)
{

  /* USER CODE BEGIN 1 */
  /* 若用cubemx重新生成配置后，需要修改sdio.c内
      hsd.Init.BusWide = SDIO_BUS_WIDE_4B;
      中SDIO_BUS_WIDE_4B改为SDIO_BUS_WIDE_1B。
      否则会报错无法正常运行。 */
  uint16_t ads_channel = 0x0020;
  /* USER CODE END 1 */

  /* MCU Configuration--------------------------------------------------------*/

  /* Reset of all peripherals, Initializes the Flash interface and the Systick. */
  HAL_Init();

  /* USER CODE BEGIN Init */

  /* USER CODE END Init */

  /* Configure the system clock */
  SystemClock_Config();

  /* USER CODE BEGIN SysInit */

  /* USER CODE END SysInit */

  /* Initialize all configured peripherals */
  MX_GPIO_Init();
  MX_DMA_Init();
  MX_ADC1_Init();
  MX_SDIO_SD_Init();
  MX_SPI1_Init();
  MX_SPI2_Init();
  MX_USART3_UART_Init();
  MX_USART2_UART_Init();
  MX_TIM6_Init();
  MX_TIM1_Init();
  MX_TIM2_Init();
  MX_TIM4_Init();
  /* USER CODE BEGIN 2 */
	SwitchOn(100);
	detect_battery_status();
	HAL_TIM_Base_Start_IT(&htim6);
	nirs_init();
	DebugPrintf("stm32 init done.");
//  ads1258init();
//  set_ads_channel(&ads_channel);
//  ADS1258_START(HIGH);
  /* USER CODE END 2 */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
  while (1)
  {
    
//    for(uint8_t i = 0; i<4; i++){
//      tlcSetGS(i, 0x0fff, 1, 1);
//      HAL_Delay(10);
//      tlcSetGS(i, 0x0fff, 0, 1);
//      HAL_Delay(10);
//    }
    /* 检查UART接收是否完成 */
    if (g_uart_rx_buffer.data_ready_flag) {
        /* 输出接收到的数据长度信息 */
        //DebugPrintf("UART received %d bytes of data", g_uart_rx_buffer.write_index);
        
        /* 清除接收完成标志，准备接收下一帧数据 */
        g_uart_rx_buffer.data_ready_flag = 0;
        
        /* 设置白色LED指示接收到数据 */
        set_led_color('w');  /* 白色LED表示数据接收成功但尚未处理或响应 */
        
        /* 解码并处理接收到的命令 */
        decode_received_command(g_uart_rx_buffer.buffer, g_uart_rx_buffer.write_index);
    }

    /* 检查定时器是否就绪（定时触发事件） */
    if (g_timer_ready_flag) {
        uint8_t flag = g_timer_ready_flag;
        /* 清除定时器就绪标志 */
        g_timer_ready_flag = 0;
      
        /* 执行fNIRS定时器处理函数 */
          nirs_timer_handle(flag);
    }
    if(g_fnirs_ready_flag){
      nirs_data_send();
      g_fnirs_ready_flag = 0;
    }

    /* USER CODE END WHILE */

    /* USER CODE BEGIN 3 */
  }
  /* USER CODE END 3 */
}

/**
  * @brief System Clock Configuration
  * @retval None
  */
void SystemClock_Config(void)
{
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

  /** Configure the main internal regulator output voltage
  */
  __HAL_RCC_PWR_CLK_ENABLE();
  __HAL_PWR_VOLTAGESCALING_CONFIG(PWR_REGULATOR_VOLTAGE_SCALE1);

  /** Initializes the RCC Oscillators according to the specified parameters
  * in the RCC_OscInitTypeDef structure.
  */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSE;
  RCC_OscInitStruct.HSEState = RCC_HSE_ON;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSE;
  RCC_OscInitStruct.PLL.PLLM = 4;
  RCC_OscInitStruct.PLL.PLLN = 160;
  RCC_OscInitStruct.PLL.PLLP = RCC_PLLP_DIV2;
  RCC_OscInitStruct.PLL.PLLQ = 7;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {
    Error_Handler();
  }

  /** Initializes the CPU, AHB and APB buses clocks
  */
  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK
                              |RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV4;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV2;

  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_5) != HAL_OK)
  {
    Error_Handler();
  }
}

/* USER CODE BEGIN 4 */

/* USER CODE END 4 */

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void Error_Handler(void)
{
  /* USER CODE BEGIN Error_Handler_Debug */
  /* User can add his own implementation to report the HAL error return state */
  HAL_TIM_Base_Stop_IT(&htim6);
  HAL_TIM_Base_Stop_IT(&htim2);
  
	set_led_color('p');
  while (1)
  {
    SwitchOff(500);
    if(ReadKey() == 0){
      __disable_irq();
    }
  }
  /* USER CODE END Error_Handler_Debug */
}

#ifdef  USE_FULL_ASSERT
/**
  * @brief  Reports the name of the source file and the source line number
  *         where the assert_param error has occurred.
  * @param  file: pointer to the source file name
  * @param  line: assert_param error line source number
  * @retval None
  */
void assert_failed(uint8_t *file, uint32_t line)
{
  /* USER CODE BEGIN 6 */
  /* User can add his own implementation to report the file name and line number,
     ex: printf("Wrong parameters value: file %s on line %d\r\n", file, line) */
  /* USER CODE END 6 */
}
#endif /* USE_FULL_ASSERT */

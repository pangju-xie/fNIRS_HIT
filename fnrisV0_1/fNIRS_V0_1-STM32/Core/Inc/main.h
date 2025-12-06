/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.h
  * @brief          : Header for main.c file.
  *                   This file contains the common defines of the application.
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

/* Define to prevent recursive inclusion -------------------------------------*/
#ifndef __MAIN_H
#define __MAIN_H

#ifdef __cplusplus
extern "C" {
#endif

/* Includes ------------------------------------------------------------------*/
#include "stm32f4xx_hal.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */

/* USER CODE END Includes */

/* Exported types ------------------------------------------------------------*/
/* USER CODE BEGIN ET */

/* USER CODE END ET */

/* Exported constants --------------------------------------------------------*/
/* USER CODE BEGIN EC */

/* USER CODE END EC */

/* Exported macro ------------------------------------------------------------*/
/* USER CODE BEGIN EM */

/* USER CODE END EM */

/* Exported functions prototypes ---------------------------------------------*/
void Error_Handler(void);

/* USER CODE BEGIN EFP */

/* USER CODE END EFP */

/* Private defines -----------------------------------------------------------*/
#define POW_KEY_Pin GPIO_PIN_2
#define POW_KEY_GPIO_Port GPIOE
#define POW_CTRL_Pin GPIO_PIN_3
#define POW_CTRL_GPIO_Port GPIOE
#define NIRS_START_Pin GPIO_PIN_0
#define NIRS_START_GPIO_Port GPIOA
#define NIRS_CS_Pin GPIO_PIN_1
#define NIRS_CS_GPIO_Port GPIOA
#define NIRS_DRDY_Pin GPIO_PIN_4
#define NIRS_DRDY_GPIO_Port GPIOA
#define NIRS_DRDY_EXTI_IRQn EXTI4_IRQn
#define VRPG_Pin GPIO_PIN_2
#define VRPG_GPIO_Port GPIOB
#define XLAT_Pin GPIO_PIN_7
#define XLAT_GPIO_Port GPIOE
#define BLANK_Pin GPIO_PIN_8
#define BLANK_GPIO_Port GPIOE
#define WIFI_CS_Pin GPIO_PIN_12
#define WIFI_CS_GPIO_Port GPIOB
#define WIFI_DRDY_Pin GPIO_PIN_10
#define WIFI_DRDY_GPIO_Port GPIOD
#define LEDB_Pin GPIO_PIN_11
#define LEDB_GPIO_Port GPIOD
#define LEDG_Pin GPIO_PIN_12
#define LEDG_GPIO_Port GPIOD
#define LEDR_Pin GPIO_PIN_13
#define LEDR_GPIO_Port GPIOD

/* USER CODE BEGIN Private defines */

void HAL_UART_RxIdleCallback(UART_HandleTypeDef *huart);
/* USER CODE END Private defines */

#ifdef __cplusplus
}
#endif

#endif /* __MAIN_H */

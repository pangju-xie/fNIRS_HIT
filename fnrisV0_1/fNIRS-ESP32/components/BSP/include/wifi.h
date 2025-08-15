#ifndef _WIFI_H
#define _WIFI_H

#ifdef __cplusplus
extern "C"
{
#endif
#include "esp_wifi.h"

extern esp_netif_ip_info_t local_ip_info;

int wifi_init(void);

#ifdef __cplusplus
}
#endif
#endif 


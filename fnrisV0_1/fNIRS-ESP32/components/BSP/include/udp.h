#ifndef _UDP_H
#define _UDP_H

#ifdef __cplusplus
extern "C"
{
#endif

#include "stdio.h"

#define PORT0 2227
#define PORT1 1227


void udp_task(void);
ssize_t udp_safe_send(uint8_t *buf, ssize_t len);

#ifdef __cplusplus
}
#endif
#endif 

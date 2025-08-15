#ifndef WEB_SERVER_h
#define WEB_SERVER_h

#ifdef __cplusplus
extern "C"
{
#endif

void web_server_start(void);
unsigned char NVS_read_data_from_flash(char *ConfirmString,char *WIFI_Name,char *WIFI_Password);
void NVS_write_data_to_flash(char *WIFI_Name, char *WIFI_Password, char *ConfirmString);

#ifdef __cplusplus
}
#endif
#endif  
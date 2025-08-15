#include "ads1258.h"
#include "spi.h"
#include "string.h"
#include "utils.h"
#include "main.h"
#include "gpio.h"

uint8_t coutflag = 0;

uint8_t registerMap[NUM_REGISTERS];

uint8_t DataTx[20] = {0};
uint8_t DataRx[20] = {0};
uint8_t RxBuf[90]  = {0};
uint8_t StaBuf[30] = {0};
uint8_t datadone = 0;

channel_info channel;


//获取配置寄存器信息
uint8_t getRegisterValue(uint8_t address)
{
  if(address<NUM_REGISTERS){
    return registerMap[address];
  }
  else{
    DebugPrintf("ads1258 address map error.");
    return 0;
  }
}

/**
 * \fn void ads1258init(void)
 * \brief 初始化ADC
 */
void ads1258init(void)
{
	ADS1258_START(LOW);
	ADS1258_RESET(LOW);
	Delay_us(125);
	ADS1258_RESET(HIGH);
	Delay_us(25);
	if(ADS1258_ID != readSingleRegister(REG_ADDR_ID)){
		DebugPrintf("something wrong happened, spi transfer receive error.");
		Error_Handler();
	}
	/* Ensure internal register array is initialized */
	restoreRegisterDefaults();
	
	/* (OPTIONAL) Configure initial device register settings here */
	uint8_t initRegisterMap[NUM_REGISTERS];
	initRegisterMap[REG_ADDR_CONFIG0]   =   CONFIG0_BYPAS_MASK|CONFIG0_CHOP_MASK|CONFIG0_STAT_MASK;
	initRegisterMap[REG_ADDR_CONFIG1]   =   CONFIG1_DLY_0us | CONFIG1_DRATE_23739SPS;
	initRegisterMap[REG_ADDR_MUXSCH]    =   MUXSCH_DEFAULT;
	initRegisterMap[REG_ADDR_MUXDIF]    =   MUXDIF_DEFAULT;
	initRegisterMap[REG_ADDR_MUXSG0]    =   MUXSG0_DEFAULT;
	initRegisterMap[REG_ADDR_MUXSG1]    =   MUXSG1_DEFAULT;
	initRegisterMap[REG_ADDR_SYSRED]    =   SYSRED_DEFAULT;
	initRegisterMap[REG_ADDR_GPIOC]     =   0x00;
	initRegisterMap[REG_ADDR_GPIOD]     =   GPIOD_DEFAULT;
	initRegisterMap[REG_ADDR_ID]        =   0x00;           // Read-only register
	
	/* (OPTIONAL) Write to all (writable) registers */
	writeMultipleRegisters(REG_ADDR_CONFIG0, NUM_REGISTERS - 1, initRegisterMap);
	
	/* (OPTIONAL) Read back all registers */
	readMultipleRegisters(REG_ADDR_CONFIG0, NUM_REGISTERS);
	
	if(memcmp(initRegisterMap, registerMap, NUM_REGISTERS-1)){
		DebugPrintf("ads1258 init error, write register not equal to read register.");
		Error_Handler();
	}
	
}

void ads1258_setgpio(uint8_t bit, uint8_t on){
	if(on){
		SET_BIT(registerMap[REG_ADDR_GPIOD], bit);
	}
	else{
		CLEAR_BIT(registerMap[REG_ADDR_GPIOD], bit);
	}
	writeSingleRegister(REG_ADDR_GPIOD, registerMap[REG_ADDR_GPIOD]);
}


//统计通道信息
void count_channel_info(void){
	memset(&channel, 0, sizeof(channel));
	for(uint8_t i = REG_ADDR_GPIOC;i>=REG_ADDR_MUXDIF;i--){
		channel.mask = channel.mask<<8;
		channel.mask = channel.mask|registerMap[i];
	}
	for(uint8_t i = 0; i<32;i++){
		if(GetBit(channel.mask, i)){
			channel.chn_map[channel.num] = i;
			channel.num++;
		}
	}
	if(channel.num == 0){
		channel.d2chn = 0xFF;
	}
	else if(channel.num == 1){
		channel.d2chn = 0xFE;
	}
	else{
		channel.d2chn = channel.chn_map[channel.num-2];
	}
}

//调整通道开关
void set_ads_channel(uint16_t* buf_cfg){

	writeMultipleRegisters(REG_ADDR_MUXSG0, 2, (uint8_t*)buf_cfg);
	readMultipleRegisters(REG_ADDR_MUXSG0, 2);
	count_channel_info();
}

/**
 * \fn uint8_t readSingleRegister(uint8_t addr)
 * \brief Reads contents of a single register at the specified address
 * \param addr address of the register to read
 * \return 8-bit register read result
 */
uint8_t readSingleRegister(uint8_t address)
{
	/* Initialize arrays */
	uint8_t DataTx[2] = { 0 };
	uint8_t DataRx[2] = { 0 };
	
	/* Build TX array and send it */
	DataTx[0] = OPCODE_RREG | (address & OPCODE_A_MASK);
	
	ADS1258_CS(LOW);
	HAL_SPI_TransmitReceive(&ADS1258_SPI, DataTx, DataRx, 2, 100);
	ADS1258_CS(HIGH);
	
	/* Update register array and return read result*/
	registerMap[address] = DataRx[1];
	return DataRx[1];
}



/**
 * \fn void readMultipleRegisters(uint8_t startAddress, uint8_t count)
 * \brief Reads a group of registers starting at the specified address
 * \param startAddress register address from which we start reading
 * \param count number of registers we want to read
 * NOTE: Use getRegisterValue() to retrieve the read values
 */
void readMultipleRegisters(uint8_t startAddress, uint8_t count)
{
	uint8_t DataTx[20] = {0};
	uint8_t DataRx[20] = {0};
	DataTx[0] = OPCODE_RREG | OPCODE_MUL_MASK | (startAddress & OPCODE_A_MASK);
	
	ADS1258_CS(LOW);
	
	HAL_SPI_TransmitReceive(&ADS1258_SPI, DataTx, DataRx, count+1, 100);
	
	ADS1258_CS(HIGH);
	memcpy(registerMap+startAddress, DataRx+1, count);
}



/**
 * \fn void writeSingleRegister(uint8_t address, uint8_t data)
 * \brief Write data to a single register at the specified address
 * \param address The address of the register to write
 * \param data The 8-bit data to write to the register
 */
void writeSingleRegister(uint8_t address, uint8_t data)
{
	/* Initialize arrays */
	uint8_t DataTx[2];
	uint8_t DataRx[2] = { 0 };
	
	/* Build TX array and send it */
	DataTx[0] = ( OPCODE_WREG | (address & OPCODE_A_MASK) );
	DataTx[1] = data;
	
	ADS1258_CS(LOW);
	HAL_SPI_TransmitReceive(&ADS1258_SPI, DataTx, DataRx, 2, 100);
	//spiSendReceiveArrays(DataTx, DataRx, 2);
	ADS1258_CS(HIGH);
	
	/* Update register array */
	registerMap[address] = DataTx[1];
}



/**
 * \fn void writeMultipleRegisters(uint8_t startAddress, uint8_t count, const uint8_t regData[])
 * \brief Writes data to a group of registers
 * \param startAddress register address from which we start write
 * \param count number of registers we want to write to
 * \param regData Array that holds the data to write, where element zero is the data to write to the starting address.
 * NOTES:
 * - Use getRegisterValue() to retrieve the written values.
 * - Registers should be re-read after a write operaiton to ensure proper configuration.
 */
void writeMultipleRegisters(uint8_t startAddress, uint8_t count, uint8_t regData[])
{
	uint8_t DataTx[20] = {0};
	uint8_t DataRx[20] = {0};
	DataTx[0] = OPCODE_WREG | OPCODE_MUL_MASK | (startAddress & OPCODE_A_MASK);
	memcpy(DataTx+1, regData, count);
	
	ADS1258_CS(LOW);	
	HAL_SPI_TransmitReceive(&ADS1258_SPI, DataTx, DataRx, count+1, 100);
	ADS1258_CS(HIGH);
	memcpy(registerMap+startAddress, regData+startAddress, count);
}



/**
 * \fn void sendCommand(uint8_t op_code)
 * \brief Sends the specified SPI command to the ADC
 * \param op_code SPI command byte
 */
void sendCommand(uint8_t op_code)
{

	/* SPI communication */
	ADS1258_CS(LOW);
	HAL_SPI_Transmit(&ADS1258_SPI, &op_code, 1, 100);
	//spiSendReceiveByte(op_code);
	ADS1258_CS(HIGH);
	
	// Check for RESET command
	if (OPCODE_RESET == op_code)
	{
		/* Update register array to keep software in sync with device */
		restoreRegisterDefaults();
	}
}



/**
 * \fn void startConversions()
 * \brief Wakes the device from power-down and starts continuous conversions
 */
void startConversions(void)
{
	ADS1258_PWDN(HIGH);/* Ensure device is not in PWDN mode */
	ADS1258_START(HIGH);/* Begin continuous conversions */
}

void stopConversions(void){
	ADS1258_START(LOW);
}



float ReadDataDirect(uint8_t data[]){
	//static uint16_t flag = 0;
	uint8_t chn = 0;
	uint8_t DataTx[4] = { 0 };    // Initialize all array elements to 0
	uint8_t DataRx[4] = { 0 };    // Relies on C99 [$6.7.8/10], [$6.7.8/21]
	float f_value = 0.0f;
	DataTx[0] = OPCODE_READ_DIRECT;
	
	Delay_us(1);
	ADS1258_CS(LOW);
	HAL_SPI_TransmitReceive(&ADS1258_SPI, DataTx, DataRx, 4, 100);

	ADS1258_CS(HIGH);
	chn = (DataRx[0]&STATUS_CHID_MASK);
	for(uint8_t i = 0; i<channel.num;i++){
		if(chn == channel.chn_map[i]){
			memcpy(data+i*3, DataRx+1,3);
			f_value = DataConvert(chn, data +i*3);
			break;
		}
	}

	if(channel.num>1 && chn == channel.d2chn){
		ADS1258_START(LOW);
		datadone = 1;
	}
	return f_value;
}

void ReadDataCommand(uint8_t data[]){

	uint8_t chn = 0;
	uint8_t DataTx[5] = { 0 };    // Initialize all array elements to 0
	uint8_t DataRx[5] = { 0 };    // Relies on C99 [$6.7.8/10], [$6.7.8/21]
	DataTx[0] = OPCODE_READ_COMMAND | OPCODE_MUL_MASK;
	
	ADS1258_CS(LOW);
	HAL_SPI_TransmitReceive(&ADS1258_SPI, DataTx, DataRx, 5, 100);
	ADS1258_CS(HIGH);
	
	chn = DataRx[1]&STATUS_CHID_MASK;
	for(uint8_t i = 0; i<channel.num;i++){
		if(chn == channel.chn_map[i]){
			memcpy(data+i*3, DataRx+2,3);
			break;
		}
	}
}

float DataConvert(uint8_t chn, uint8_t data[]){
	static float offset = 0.0f;
	static float vcc = 5.0f;
	static float temp = 0.0f;
	static float gain = 0.999f;
	static float ref = 5.0f;
	float convert = 0.0f;
	if(chn>STATUS_CHID_FIXEDCHMODE){
		DebugPrintf("chn num error.\r\n");
		Error_Handler();
		return 0;
	}
	uint32_t Value = (data[0]<<16)|(data[1]<<8|data[2]);
	if(chn == STATUS_CHID_OFFSET){
		offset = Value/1.0f;
		DebugPrintf("offset value:0x%x,%.3f\r\n", Value, offset);
	}
	else if(chn == STATUS_CHID_VCC){
		vcc = Value/786432.0f;
		DebugPrintf("vcc value:0x%x,%.3f\r\n", Value, vcc);
	}
	else if(chn == STATUS_CHID_TEMP){
		Value = (Value&0x800000)?(0xffffff-Value):(Value);
		temp = (((float)(Value/0x780000)*ref)*1000000-168000)/563 + 25;
		DebugPrintf("temp value:0x%x,%.3f\r\n", Value, temp);
	}
	else if(chn == STATUS_CHID_GAIN){
		gain = Value/7864320.0f;
		DebugPrintf("gain value:0x%x,%.3f\r\n", Value, gain);
	}
	else if(chn == STATUS_CHID_REF){
		ref = Value/786432.0f;
		DebugPrintf("ref value:0x%x,%.3f\r\n", Value, ref);
	}
	else if(chn<STATUS_CHID_AIN15){
		if(Value&0x800000){
			convert = ((float)(0xffffff-Value)/(float)0x780000)*ref/gain;
			convert = -convert;
		}
		else{
			convert = ((float)Value/(float)0x780000)*ref/gain*1000;
		}
		if(chn<STATUS_CHID_DIFF7){
			DebugPrintf("dual channel %d, value:0x%x, %.2f\r\n", chn, Value, convert);
		}
		else{
			//DebugPrintf("schn %d:0x%x, %.2f. ", chn-STATUS_CHID_DIFF7, Value, convert);
			DebugPrintf("schn %d:%.2f. \r\n", chn-STATUS_CHID_DIFF7, convert);
		}
	}
	return convert;
}


/**
 * \fn void restoreRegisterDefaults(void)
 * \brief Updates the registerMap[] array to its default values.
 *
 * NOTES:
 * - If the MCU keeps a copy of the ADC register settings in memory,
 * then it is important to ensure that these values remain in sync with the
 * actual hardware settings. In order to help facilitate this, this function
 * should be called after powering up or resetting the device (either by
 * hardware pin control or SPI software command).
 *
 * - Reading back all of the registers after resetting the device will
 * accomplish the same result.
 */
void restoreRegisterDefaults(void)
{
	registerMap[REG_ADDR_CONFIG0]   =   CONFIG0_DEFAULT;
	registerMap[REG_ADDR_CONFIG1]   =   CONFIG1_DEFAULT;
	registerMap[REG_ADDR_MUXSCH]    =   MUXSCH_DEFAULT;
	registerMap[REG_ADDR_MUXDIF]    =   MUXDIF_DEFAULT;
	registerMap[REG_ADDR_MUXSG0]    =   MUXSG0_DEFAULT;
	registerMap[REG_ADDR_MUXSG1]    =   MUXSG1_DEFAULT;
	registerMap[REG_ADDR_SYSRED]    =   SYSRED_DEFAULT;
	registerMap[REG_ADDR_GPIOC]     =   GPIOC_DEFAULT;
	registerMap[REG_ADDR_GPIOD]     =   GPIOD_DEFAULT;
	registerMap[REG_ADDR_ID]        =   0x00;               // Value of 0x00 indicates that we have not yet read the ID register
}

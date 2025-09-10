#ifndef _THATCLOCK_PARSEDATA_H
#define _THATCLOCK_PARSEDATA_H

#include <String.h>
#include <ArduinoJson.h>
#include <stdint.h>
#include <ui.h>
#include <lvgl.h>
#include <HTTPClient.h>

typedef struct CalendarData{
	const char* gregorian;
	const char* weekday;
	int solar_year;
	uint8_t solar_month;
	uint8_t solar_day;
	char* solar_term;
	int lunar_year;
	uint8_t lunar_month;
	uint8_t lunar_day;
	const char* lunar_zodiac;
} CalendarData;

typedef struct Weather{
	short weather_types;
	uint8_t day;
	uint8_t month;
	uint8_t year;
	uint8_t precipitation;
	float temp_max;
	float temp_min;
	const char* descriptions;
} Weather;

typedef struct WeatherData{
	Weather** weather_pkg;
	const char* district;
	const char* location;
} WeatherData;

const char* const TERM_NAMES[] PROGMEM = {
    "小寒", "大寒", "立春", "雨水", "驚蟄", "春分", "清明", "谷雨", "立夏", "小滿", "芒種", "夏至", "小暑", "大暑",
    "立秋", "處暑", "白露", "秋分", "寒露", "霜降",  "立冬", "小雪", "大雪", "冬至"
};

const char* const MONTH_NAMES[] PROGMEM = {
    "JANUARY", "FEBRUARY", "MARCH",     "APRIL",   "MAY",      "JUNE",
    "JULY",    "AUGUST",   "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"
};

const char* const MONTH_NAMES_STD[] PROGMEM = {
    "January", "February", "March",     "April",   "May",      "June",
    "July",    "August",   "September", "October", "November", "December"
};

// Server request address
const String serverURL = {Your Server Address Here};

CalendarData* parseCalendarData(String jsonStr);
char* parseMonthInString(uint8_t month);
bool updateTheDate(bool haveSynchronized_server);
WeatherData* parseWeatherData(String jsonStr);
void cleanup(WeatherData* data);
bool updateTheWeather(bool haveSynchronized_server);

#endif
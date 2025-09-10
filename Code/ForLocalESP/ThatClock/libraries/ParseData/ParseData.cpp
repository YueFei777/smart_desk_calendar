#include "ParseData.h"

/*paraphrase the JSON package: Time related*/
CalendarData* parseCalendarData(String jsonStr){
	CalendarData* calendarData = (CalendarData*)malloc(sizeof(CalendarData));
	
	const size_t capacity = JSON_OBJECT_SIZE(5) + JSON_OBJECT_SIZE(4) * 2 + 1024;
	StaticJsonDocument<capacity> doc;
	
	DeserializationError error = deserializeJson(doc, jsonStr);

	if(error){
		free(calendarData);
		return NULL;
	}
	
	calendarData->gregorian = doc["gregorian"];
	calendarData->weekday = doc["weekday"];
	
	JsonObject solar = doc["solar"];
	calendarData->solar_year = solar["year"];
	calendarData->solar_month = solar["month"];
	calendarData->solar_day = solar["day"];
	
	static char buffer[8];
	short solar_term_index = solar["solar_term"];
	strcpy_P(buffer, (const char*)pgm_read_ptr(&TERM_NAMES[solar_term_index]));
	calendarData->solar_term = buffer;
	
	JsonObject lunar = doc["lunar"];
	calendarData->lunar_year = lunar["year"];
	calendarData->lunar_month = lunar["month"];
	calendarData->lunar_day = lunar["day"];
	calendarData->lunar_zodiac = lunar["zodiac"];
	
	return calendarData;
}

WeatherData* parseWeatherData(String jsonStr){
	// initialize
	WeatherData* weatherData = (WeatherData*)malloc(sizeof(WeatherData));
	if (!weatherData) return nullptr;

    Weather** weather_info = (Weather**)malloc(sizeof(Weather*) * 5);
    if (!weather_info) {
        free(weatherData);
        return nullptr;
    }
	
	 for (int i = 0; i < 5; i++) {
        weather_info[i] = (Weather*)malloc(sizeof(Weather));
        if (!weather_info[i]) {
            for (int j = 0; j < i; j++) free(weather_info[j]);
            free(weather_info);
            free(weatherData);
            return nullptr;
        }
    }
	weatherData->weather_pkg = weather_info;
	
	StaticJsonDocument<1536> doc;
    DeserializationError error = deserializeJson(doc, jsonStr);
	 if (error) {
        Serial.print(F("deserializeJson() failed: "));
        Serial.println(error.c_str());
        cleanup(weatherData);
        return nullptr;
    }
	JsonArray forecast = doc["forecast"];
	weatherData->district = strdup(doc["district"]);
	weatherData->location = strdup(doc["location"]);
	
	 for (size_t i = 0; i < forecast.size() && i < 5; i++) {
        JsonObject item = forecast[i];
        
        weather_info[i]->day = item["day"].as<uint8_t>();
        weather_info[i]->month = item["month"].as<uint8_t>();
        weather_info[i]->year = item["year"].as<uint8_t>();
        weather_info[i]->precipitation = item["precipitation"].as<uint8_t>();
        weather_info[i]->temp_max = item["temperature_max"];
        weather_info[i]->temp_min = item["temperature_min"];
        weather_info[i]->weather_types = item["weather_type"];
        weather_info[i]->descriptions = strdup(item["descriptions"]);
    }

    return weatherData;
}

void cleanup(WeatherData* data) {
    if (data) {
        free((void*)data->district);
        free((void*)data->location);
        
        if (data->weather_pkg) {
            for (int i = 0; i < 5; i++) {
                if (data->weather_pkg[i]) {
                    free((void*)data->weather_pkg[i]->descriptions);
                    free(data->weather_pkg[i]);
                }
            }
            free(data->weather_pkg);
        }
        free(data);
    }
}

char* parseMonthInString(uint8_t month){
	static char buffer[12];
	strcpy_P(buffer, (const char*)pgm_read_ptr(&MONTH_NAMES[month - 1]));
	return buffer;
}

bool updateTheDate(bool haveSynchronized_server){
	HTTPClient http;
	http.begin(serverURL + "/time");

	int httpCode = http.GET();
	if (httpCode == HTTP_CODE_OK){
		String payload = http.getString();
		CalendarData* calendarData = parseCalendarData(payload);

		// Update the date on main screen
		lv_label_set_text_fmt(ui_DateLabel, "%d/%02d/%02d, %s", calendarData->solar_year, calendarData->solar_month, calendarData->solar_day, calendarData->weekday);

		// Update the calendar
		lv_label_set_text(ui_CalendarCharacter, (const char*)parseMonthInString(calendarData->solar_month)); // Set month string_en
		lv_label_set_text_fmt(ui_CalendarDigit, "%02d", calendarData->solar_day); // Set day string_en
		if(calendarData->lunar_month == 12 && calendarData->lunar_day == 31 || !haveSynchronized_server){ //Set year string_zh only when the year is about to pass
			lv_label_set_text_fmt(ui_YearValueZH, "%d年", calendarData->lunar_year);
		}
		lv_label_set_text_fmt(ui_DateValueZH, "%02d月%02d日", calendarData->lunar_month, calendarData->lunar_day); // Set month string_zh
		lv_label_set_text(ui_TermValueZH, calendarData->solar_term); // Set day string_zh
		
		free((void*)calendarData);
		
		return true;
	}
	
	return false;
}

bool updateTheWeather(bool haveSynchronized_server){
	HTTPClient http;
	http.begin(serverURL + "/weather");

	int httpCode = http.GET();
	if (httpCode == HTTP_CODE_OK){
		String payload = http.getString();
		WeatherData* weatherData = parseWeatherData(payload);
		if(weatherData == nullptr){
			goto failed;
		} else {
			// Update the weather forecast
            Weather** forecasts = weatherData->weather_pkg;
            lv_obj_t* uiElements[5][5] = {
                {ui_WeatherIconLabel1, ui_Temperature1, ui_Precipitation1, ui_WeatherIcon1, ui_WeatherLabel1},
                {ui_WeatherIconLabel2, ui_Temperature2, ui_Precipitation2, ui_WeatherIcon2, ui_WeatherLabel2},
                {ui_WeatherIconLabel3, ui_Temperature3, ui_Precipitation3, ui_WeatherIcon3, ui_WeatherLabel3},
                {ui_WeatherIconLabel4, ui_Temperature4, ui_Precipitation4, ui_WeatherIcon4, ui_WeatherLabel4},
				{ui_WeatherIconLabel5, ui_Temperature5, ui_Precipitation5, ui_WeatherIcon5, ui_WeatherLabel5}
			};
            
			for (int i = 0; i < 5 && forecasts[i] != nullptr; i++) {
				// Update the type of weather
				lv_label_set_text(uiElements[i][0], forecasts[i]->descriptions);
				
				// Update the icon of weather
				lv_img_set_src(uiElements[i][3], img_icon_option[forecasts[i]->weather_types - 1]);
				
				// Update the date of weather
				lv_label_set_text_fmt(uiElements[i][4], "%s, %d", 
									MONTH_NAMES_STD[forecasts[i]->month - 1],
									forecasts[i]->day);
				
				// Update the temperature
				lv_label_set_text_fmt(uiElements[i][1], "%.1f~%.1f °C", 
									forecasts[i]->temp_min,
									forecasts[i]->temp_max);
				
				// Update the precipitation
				lv_label_set_text_fmt(uiElements[i][2], "%.1f%%", 
									 forecasts[i]->precipitation);
			}
			cleanup(weatherData); // release the storage
			lv_label_set_text(ui_WeatherRefreshNoticeLabel, "Update Successfully!");
			lv_obj_clear_flag(ui_WeatherRefreshAcceptIcon, LV_OBJ_FLAG_HIDDEN);
			lv_obj_add_flag(ui_WeatherRefreshNoticeSpinner, LV_OBJ_FLAG_HIDDEN);
			/* WeatherRefreshNotice_Animation(ui_WeatherRefreshNotice, 0); 
			delay(2000);
			WeatherRefreshNoticeUp_Animation(ui_WeatherRefreshNotice, 0); 
			lv_obj_add_flag(ui_WeatherRefreshAcceptIcon, LV_OBJ_FLAG_HIDDEN);
			lv_obj_clear_flag(ui_WeatherRefreshNoticeSpinner, LV_OBJ_FLAG_HIDDEN);
			lv_label_set_text(ui_WeatherRefreshNoticeLabel, "Refreshing..."); */
			return true;
		}
	}
	
	failed:
	/* lv_label_set_text(ui_WeatherRefreshNoticeLabel, "Update Failed!");
	lv_obj_clear_flag(ui_WeatherRefreshDeclineIcon, LV_OBJ_FLAG_HIDDEN);
	lv_obj_add_flag(ui_WeatherRefreshNoticeSpinner, LV_OBJ_FLAG_HIDDEN);
	delay(1200);
	WeatherRefreshNoticeUp_Animation(ui_WeatherRefreshNotice, 0);
	lv_obj_add_flag(ui_WeatherRefreshDeclineIcon, LV_OBJ_FLAG_HIDDEN);
	lv_obj_clear_flag(ui_WeatherRefreshNoticeSpinner, LV_OBJ_FLAG_HIDDEN);
	lv_label_set_text(ui_WeatherRefreshNoticeLabel, "Refreshing..."); */
	return false;
}
#include <lvgl.h>
#include <TFT_eSPI.h>
#include <ui.h>
#include <XPT2046_Touchscreen.h>
#include <sys/time.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ParseData.h>
#include <HardwareSerial.h>

/*Don't forget to set Sketchbook location in File/Preferences to the path of your UI project (the parent folder of this INO file)*/

/*Change to your screen resolution*/
#define SCREEN_WIDTH 240
#define SCREEN_HEIGHT 320

// Touchscreen pins
#define XPT2046_IRQ  1   // T_IRQ
#define XPT2046_MOSI  6  // T_DIN
#define XPT2046_MISO  3  // T_OUT
#define XPT2046_CLK 5   // T_CLK
#define XPT2046_CS  4    // T_CS

// NTP setup
#define GMT_OFFSET_SEC 8 * 3600
#define DAYLIGHT_OFFSET_SEC 0

#define DRAW_BUF_SIZE (SCREEN_WIDTH * SCREEN_HEIGHT / 10 * (LV_COLOR_DEPTH / 8))
uint32_t draw_buf[DRAW_BUF_SIZE / 4];

int x, y, z;

// WiFi configuration
const char* ssid = "{IP name}";
const char* password = "{IP password}";
const char* ntpServer = "pool.ntp.org"; // NTP Server
const char* ntpServerBackup = "ntp2.aliyun.com"; // NTP Server backup
bool haveSynchronized = false;
bool haveSynchronized_server = false;

// Alarm configuration
bool alarmSet = 0; // Alarm enable flag
int RollbarSetHour = 0;
int RollbarSetMin = 0;
int RollbarSetSec = 0;

// UART stuff
char msg[64] = {0};
volatile bool receivedFlag = false;
volatile short recvIndex = 0;

uint8_t currentRing = 0x00;

// Time sync management
unsigned long lastReconnectAttempt = 0;
unsigned long lastSyncAttempt = 0;
const unsigned long RECONNECT_INTERVAL = 30 * 1000; // reconnect after 30 seconds
const unsigned long SYNC_INTERVAL = 60 * 60 * 1000; // synchronize every 1 hour

enum WiFiState {
  WIFI_DISCONNECTED,
  WIFI_CONNECTING,
  WIFI_CONNECTED
};

WiFiState wifiState = WIFI_DISCONNECTED;

SPIClass touchscreenSPI = SPIClass(VSPI);
XPT2046_Touchscreen touchscreen(XPT2046_CS, XPT2046_IRQ);
HardwareSerial SerialPort(2);

/*Read the touchpad*/
void my_touchpad_read (lv_indev_t * indev_driver, lv_indev_data_t * data)
{
   // Checks if Touchscreen was touched, and prints X, Y and Pressure (Z)
  if(touchscreen.tirqTouched() && touchscreen.touched()) {
    // Get Touchscreen points
    TS_Point p = touchscreen.getPoint();
    // Calibrate Touchscreen points with map function to the correct width and height
    x = map(p.x, 200, 3700, 1, SCREEN_WIDTH);
    y = map(p.y, 240, 3800, 1, SCREEN_HEIGHT);
    z = p.z;

    data->state = LV_INDEV_STATE_PR;

    // Set the coordinates
    data->point.x = x;
    data->point.y = y;
  } else {
    data->state = LV_INDEV_STATE_REL;
  }
}


void WiFi_connection_mark_switch(bool isConnected, lv_obj_t* ui_Disconnected, lv_obj_t* ui_Connected){
  if(isConnected){
    lv_obj_add_state(ui_Connected, LV_STATE_USER_1);
    lv_obj_add_state(ui_Disconnected, LV_STATE_USER_1);
  } else {
    lv_obj_clear_state(ui_Disconnected, LV_STATE_USER_1);
    lv_obj_clear_state(ui_Connected, LV_STATE_USER_1);    
  }
}

/*Send data by serial bus*/
void sendDataToSerial(const char* data) {
  if (data && SerialPort.availableForWrite()) {
    SerialPort.println(data);
  }
}

void sendByteArray(uint8_t value) {
  uint8_t frame[] = {0xAA, value, 0xCC};
  SerialPort.write(frame, sizeof(frame));
}

/*Set tick routine needed for LVGL internal timings*/
static uint32_t my_tick_get_cb (void) { return millis(); }

void setup ()
{
    Serial.begin( 115200 ); /* prepare for possible serial debug */
    SerialPort.begin(9600, SERIAL_8N1, 18, 17);

    // WiFi configuration & NTC Setup
    setenv("TZ", "CST-8", 1); // Timezone setup
    tzset();

    lv_init();

    // Start the SPI for the touchscreen and init the touchscreen
    touchscreenSPI.begin(XPT2046_CLK, XPT2046_MISO, XPT2046_MOSI, XPT2046_CS);
    touchscreen.begin(touchscreenSPI);
    touchscreen.setRotation(0);

    // Create a display object
    lv_display_t * disp;
    // Initialize the TFT display using the TFT_eSPI library
    disp = lv_tft_espi_create(SCREEN_WIDTH, SCREEN_HEIGHT, draw_buf, sizeof(draw_buf));
    lv_display_set_rotation(disp, LV_DISPLAY_ROTATION_270);

    static lv_indev_t* indev;
    indev = lv_indev_create();
    lv_indev_set_type(indev, LV_INDEV_TYPE_POINTER);
    lv_indev_set_read_cb(indev, my_touchpad_read);

    lv_tick_set_cb(my_tick_get_cb);

    ui_init();

    Serial.println("Setup completed, Starting WiFi connection...\n");

    WiFi.mode(WIFI_STA);
    WiFi.begin(ssid, password);
    wifiState = WIFI_CONNECTING;

}

void readSerialData() {
  while (SerialPort.available()) {
    char c = SerialPort.read();
    if (recvIndex < sizeof(msg) - 1) {
      msg[recvIndex++] = c;
    }
    if (c == '\n') {
      msg[recvIndex] = '\0';
      receivedFlag = true;
      recvIndex = 0;
    }
  }
}

void manageWiFiConnection() {
  static unsigned long lastAttemptTime = 0;
  const unsigned long currentTime = millis();

  if(wifiState == WIFI_CONNECTING) {
    if (WiFi.status() == WL_CONNECTED) {
      Serial.println("\nWiFi connected! IP: " + WiFi.localIP().toString());
      wifiState = WIFI_CONNECTED;

      // Set up time synchronization service
      configTime(GMT_OFFSET_SEC, DAYLIGHT_OFFSET_SEC, ntpServer, ntpServerBackup);
      haveSynchronized = false; // Wait for time sync verification
    }
    else if (currentTime - lastAttemptTime > 10000) {
      Serial.println("WiFi connection attempt timed out.");
      wifiState = WIFI_DISCONNECTED;

      // Set as default time
      struct timeval tv = {0, 0};
      settimeofday(&tv, NULL);
    }

    return;
  }

  if (wifiState == WIFI_DISCONNECTED) {
    if (currentTime - lastAttemptTime > 30000) {
      Serial.println("Attempting WiFi connection...");
      WiFi.disconnect();
      WiFi.begin(ssid, password);
      wifiState = WIFI_CONNECTING;
      lastAttemptTime = currentTime;
    }

    return;
  }

  if (wifiState == WIFI_CONNECTED && WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi connection lost!\n");
    wifiState = WIFI_DISCONNECTED;

    return;
  }
}

void manageTimeSync() {
  if (wifiState != WIFI_CONNECTED) return;

  static unsigned long lastTimeCheck = 0;
  static unsigned long lastWeatherUpdate = 0;
  const unsigned long currentTime = millis();

  // Time sync verification
  if (!haveSynchronized && currentTime - lastTimeCheck >= 5000) {
    lastTimeCheck = currentTime;

    struct tm timeinfo;
    if (getLocalTime(&timeinfo, 100)) {
      if (timeinfo.tm_year > (2024 - 1900)) {
        Serial.println("Time sync verified successfully!\n");
        haveSynchronized = true;
      }
    } else {
      Serial.println("Warning: Failed to get local time.\n");
    }
  }

  // Weather update logic (hourly)
  if (currentTime - lastWeatherUpdate >= 3600000UL || (!haveSynchronized_server && currentTime - lastWeatherUpdate >= 60000UL)) { // 1 hour
    Serial.println("[TimeSync] Starting weather update");
    
    bool dateUpdated = updateTheDate(haveSynchronized_server);
    bool weatherUpdated = updateTheWeather(haveSynchronized_server);
    
    if (weatherUpdated) {
      haveSynchronized_server = true;
      Serial.println("[TimeSync] Weather updated successfully");
    } else {
      Serial.println("[TimeSync] Weather update failed");
    }
    
    lastWeatherUpdate = currentTime;
  }
}

void loop ()
{
    lv_timer_handler(); /* Handle GUI */
    delay(5);

    manageWiFiConnection();
    manageTimeSync();   /* Handle time synchronization */

    // Update time display every second
    static unsigned long lastUpdateTime = 0;
    unsigned long currentTime = millis();
    if (currentTime - lastUpdateTime >= 1000) {
      lastUpdateTime = currentTime;
      
      // Get and display time
      struct tm timeinfo;
      if(getLocalTime(&timeinfo, 100)) { // 100ms timeout
        // Update 24-hour format display
        lv_label_set_text_fmt(ui_TimeBlock, "%02d:%02d", timeinfo.tm_hour, timeinfo.tm_min);
        
        // Update 12-hour format display (handle midnight case)
        int hour12 = timeinfo.tm_hour > 12 ? timeinfo.tm_hour - 12 : 
                       (timeinfo.tm_hour == 0 ? 12 : timeinfo.tm_hour);
        lv_label_set_text_fmt(ui_TimeBlock12H, "%02d:%02d", hour12, timeinfo.tm_min);
        
        // Update AM/PM indicator
        lv_label_set_text(ui_LabelFor12H, timeinfo.tm_hour >= 12 ? "PM" : "AM");
        
        // Check alarm
        if(alarmSet && 
           timeinfo.tm_hour == RollbarSetHour && 
           timeinfo.tm_min == RollbarSetMin && 
           timeinfo.tm_sec == RollbarSetSec) {
          sendByteArray(currentRing);
          lv_obj_send_event(ui_TimesUpFlag, LV_EVENT_VALUE_CHANGED, NULL);
          Serial.println("Alarm triggered!");
        }
      }

      // Update WiFi status display
      WiFi_connection_mark_switch(wifiState == WIFI_CONNECTED, ui_Disconnected, ui_Connected);
      
      // Process temperature and humidity data
      readSerialData();   /* Process serial data */
      if(receivedFlag) {
        float temperature = 0.0;
        float humidity = 0.0;
        if (sscanf(msg, "%f, %f", &temperature, &humidity) == 2) {
          lv_label_set_text_fmt(ui_Label34, "%.1f°C", temperature);
          lv_label_set_text_fmt(ui_Label1, "%.1f%%", humidity);
        }
        receivedFlag = false;
      }
    }
}
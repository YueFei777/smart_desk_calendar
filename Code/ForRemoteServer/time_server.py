from datetime import datetime
from flask import Flask, jsonify, request
from lunarcalendar import Solar, Converter
import requests
import logging

# config log system
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('weather_api.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

IPGEO_API_KEY = {YOUR_API_KEY_HERE}
GOOGLE_WEATHER_API_KEY = {YOUR_API_KEY_HERE}

app = Flask(__name__)

solar_terms_2025 = [
    {"name": "Minor Cold", "date": "2025-01-05", "time": "10:33"},
    {"name": "Major Cold", "date": "2025-01-20", "time": "04:00"},
    {"name": "Beginning of Spring", "date": "2025-02-03", "time": "22:10"},
    {"name": "Rain Water", "date": "2025-02-18", "time": "18:07"},
    {"name": "Awakening of Insects", "date": "2025-03-05", "time": "16:07"},
    {"name": "Spring Equinox", "date": "2025-03-20", "time": "17:01"},
    {"name": "Pure Brightness", "date": "2025-04-04", "time": "20:49"},
    {"name": "Grain Rain", "date": "2025-04-20", "time": "03:56"},
    {"name": "Beginning of Summer", "date": "2025-05-05", "time": "13:57"},
    {"name": "Grain Full", "date": "2025-05-21", "time": "02:55"},
    {"name": "Grain in Ear", "date": "2025-06-05", "time": "17:57"},
    {"name": "Summer Solstice", "date": "2025-06-21", "time": "10:42"},
    {"name": "Minor Heat", "date": "2025-07-07", "time": "04:05"},
    {"name": "Major Heat", "date": "2025-07-22", "time": "21:29"},
    {"name": "Beginning of Autumn", "date": "2025-08-07", "time": "13:52"},
    {"name": "End of Heat", "date": "2025-08-23", "time": "04:34"},
    {"name": "White Dew", "date": "2025-09-07", "time": "16:52"},
    {"name": "Autumn Equinox", "date": "2025-09-23", "time": "02:19"},
    {"name": "Cold Dew", "date": "2025-10-08", "time": "08:41"},
    {"name": "Frost's Descent", "date": "2025-10-23", "time": "11:51"},
    {"name": "Beginning of Winter", "date": "2025-11-07", "time": "12:04"},
    {"name": "Minor Snow", "date": "2025-11-22", "time": "09:36"},
    {"name": "Major Snow", "date": "2025-12-07", "time": "05:05"},
    {"name": "Winter Solstice", "date": "2025-12-21", "time": "23:03"}
]

weather_image_mapping = {
    "CLEAR": 3,
    "MOSTLY_CLEAR": 2,
    "PARTLY_CLOUDY": 15,
    "MOSTLY_CLOUDY": 20,
    "CLOUDY": 17,
    
    "WINDY": 17,
    "WIND_AND_RAIN": 18,
    
    "LIGHT_RAIN_SHOWERS": 12,
    "CHANCE_OF_SHOWERS": 12,
    "SCATTERED_SHOWERS": 14,
    "RAIN_SHOWERS": 9,
    "HEAVY_RAIN_SHOWERS": 13,
    "LIGHT_TO_MODERATE_RAIN": 12,
    "MODERATE_TO_HEAVY_RAIN": 13,
    "RAIN": 14,
    "LIGHT_RAIN": 12,
    "HEAVY_RAIN": 13,
    "RAIN_PERIODICALLY_HEAVY": 13,
    
    "LIGHT_SNOW_SHOWERS": 6,
    "CHANCE_OF_SNOW_SHOWERS": 6,
    "SCATTERED_SNOW_SHOWERS": 8,
    "SNOW_SHOWERS": 19,
    "HEAVY_SNOW_SHOWERS": 7,
    "LIGHT_TO_MODERATE_SNOW": 6,
    "MODERATE_TO_HEAVY_SNOW": 7,
    "SNOW": 8,
    "LIGHT_SNOW": 6,
    "HEAVY_SNOW": 7,
    "SNOWSTORM": 19,
    "SNOW_PERIODICALLY_HEAVY": 7,
    "HEAVY_SNOW_STORM": 19,
    "BLOWING_SNOW": 8,
    
    "RAIN_AND_SNOW": 10,
    "HAIL": 14,
    "HAIL_SHOWERS": 14,
    
    "THUNDERSTORM": 21,
    "THUNDERSHOWER": 21,
    "LIGHT_THUNDERSTORM_RAIN": 21,
    "SCATTERED_THUNDERSTORMS": 21,
    "HEAVY_THUNDERSTORM": 21,
    
    "FOG": 16,
}

def log_request_details():
    logger.info(f"Received request from: {request.remote_addr}")
    logger.info(f"Request URL: {request.url}")
    logger.info(f"Request Headers: {dict(request.headers)}")
    logger.info(f"Request Method: {request.method}")
    logger.info(f"Query Parameters: {request.args}")

def get_client_ip():
    if 'X-Forwarded-For' in request.headers:
        ip = request.headers['X-Forwarded-For'].split(',')[0]
    else:
        ip = request.remote_addr
    return ip.strip()

@app.route('/time')
def get_lunar_time():
    try:
        now = datetime.now()
        solar_date = Solar(now.year, now.month, now.day)
        weekday = now.strftime("%A")
        
        lunar_date = Converter.Solar2Lunar(solar_date)
        
        zodiac_en = ["Rat", "Ox", "Tiger", "Rabbit", "Dragon", "Snake",
                    "Horse", "Goat", "Monkey", "Rooster", "Dog", "Pig"]
        zodiac = zodiac_en[(lunar_date.year - 4) % 12]
        
        # calculate current solar term
        # calculate the current solar term based on the current date and time
        current_term = None
        for i in range(len(solar_terms_2025)):
            term = solar_terms_2025[i]
            term_start = datetime.strptime(f"{term['date']} {term['time']}", "%Y-%m-%d %H:%M")
            
            # calculate the end time of the current solar term
            if i < len(solar_terms_2025)-1:
                next_term = solar_terms_2025[i+1]
                term_end = datetime.strptime(f"{next_term['date']} {next_term['time']}", "%Y-%m-%d %H:%M")
            else:
                term_end = datetime(term_start.year+1, 1, 1)
            
            if term_start <= now < term_end:
                current_term = i # the name of the current solar term will be stored at local
                break
        
        return jsonify({
            "gregorian": now.strftime("%Y-%m-%d %H:%M:%S"),
            "weekday": weekday,
            "solar": {
                "year": solar_date.year,
                "month": solar_date.month,
                "day": solar_date.day,
                "solar_term": current_term if current_term else 0
            },
            "lunar": {
                "year": lunar_date.year,
                "month": lunar_date.month,
                "day": lunar_date.day,
                "zodiac": zodiac
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/weather', methods=['GET'])
def get_weather():
    try:
        start_time = datetime.now()
        log_request_details()
        
        ip = get_client_ip()
        logger.info(f"Client IP address: {ip}")
        
        url_ip = f"https://api.ipgeolocation.io/ipgeo?apiKey={IPGEO_API_KEY}&ip={ip}"
        logger.info(f"Requesting location from: {url_ip}")
        
        geo_response = requests.get(url_ip)
        logger.info(f"Location API response status: {geo_response.status_code}")
        
        geo_data = geo_response.json()
        logger.debug(f"Location API response: {geo_data}")
        
        if not all(key in geo_data for key in ['latitude', 'longitude']):
            logger.error("Location API response missing latitude/longitude")
            logger.error(f"Full response: {geo_data}")
            return jsonify({
                "error": "Unable to retrieve location",
                "ip": ip,
                "geo_data": geo_data
            }), 400
        
        lat = geo_data['latitude']
        lon = geo_data['longitude']
        logger.info(f"Using coordinates: Latitude={lat}, Longitude={lon}")
        
        url_weather = f"https://weather.googleapis.com/v1/forecast/days:lookup?key={GOOGLE_WEATHER_API_KEY}&location.latitude={lat}&location.longitude={lon}&days=5"
        logger.info(f"Requesting weather from: {url_weather}")
        
        weather_response = requests.get(url_weather)
        logger.info(f"Weather API response status: {weather_response.status_code}")
        
        weather_data = weather_response.json()
        logger.debug(f"Weather API response: {weather_data}")
        
        if 'forecastDays' not in weather_data:
            logger.error("Weather API response missing 'forecastDays'")
            logger.error(f"Response keys: {weather_data.keys()}")
            return jsonify({
                "error": "Unable to retrieve weather data",
                "weather_response": weather_data
            }), 400
        
        # extract weather informations
        to_be_pack = []
        for day in weather_data['forecastDays']:
            transformed_day = {
                "year": day["displayDate"]["year"],
                "month": day["displayDate"]["month"],
                "day": day["displayDate"]["day"],
                "temperature_max": day["maxTemperature"]["degrees"],
                "temperature_min": day["minTemperature"]["degrees"],
                "precipitation": 
                    day["daytimeForecast"]["precipitation"]["probability"]["percent"],
                "weather_type": 
                    weather_image_mapping[day["daytimeForecast"]["weatherCondition"]["type"]],
                "descriptions": 
                    day["daytimeForecast"]["weatherCondition"]["description"]["text"]
            }
            to_be_pack.append(transformed_day)
        
        to_be_send = {
            "location": geo_data["city"],
            "district": geo_data["district"],
            "forecast": to_be_pack
        }
        
        # record processing time
        processing_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"Request processed in {processing_time:.3f} seconds")
        
        return jsonify(to_be_send)
    
    except Exception as e:
        logger.exception(f"Unexpected error in /weather endpoint: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    logger.info("Starting weather API server")
    app.run(host='0.0.0.0', port=5000, debug=False)
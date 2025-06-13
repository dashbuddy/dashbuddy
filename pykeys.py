import pgeocode, json, os

# define the file path to the json cache
CACHE_FILE = "location_cache.json"
# if the file exists, read from it and store data into variable settings,
# if not then make an empty list called settings
if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, "r") as f:
        settings = json.load(f)
else:
    settings = {}

# define variables with data from settings
country = settings["country"]
zipcode = settings["zipcode"]
units = settings["units"]

# collects longitude and latitude for the given zipcode
def get_lat_lon(zipcode):
    nomi = pgeocode.Nominatim(country)
    location = nomi.query_postal_code(zipcode)
    return (location.latitude, location.longitude)

def save_setting(key, value):
    # load the current settings
    settings = load_settings()
    # set the provided key with the provided value
    settings[key] = value
    # save that new key, value pair
    with open(CACHE_FILE, "w") as f:
        json.dump(settings, f)

def load_settings():
    try:
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JOSNDecodeError):
        return {"zipcode": "67260", "country": "us", "units": "imperial"}

lat, lon = get_lat_lon(zipcode)
weather_api_key = "9ebd97311bd90247a494f215a26e6457"
weather_daily_url = f"http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={weather_api_key}&units={units}"
weather_forecast_url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&units={units}&appid={weather_api_key}"

blackboard_ics_url = "https://blackboard.wichita.edu/webapps/calendar/calendarFeed/294b68beced847c2bbd7d40467ecfa88/learn.ics"

ui_mode = "dark"

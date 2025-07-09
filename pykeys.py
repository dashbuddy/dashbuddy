import pgeocode, json, os, secrets

# define the file path to the json cache
CACHE_FILE = "json_cache.json"

# collects longitude and latitude for the given zipcode
def get_lat_lon(zipcode):
    nomi = pgeocode.Nominatim(country)
    location = nomi.query_postal_code(zipcode)
    return (location.latitude, location.longitude)

def get_keys(key_type):
    settings = load_settings()
    if key_type not in settings and key_type == "flask_session":
        settings["flask_session"] = secrets.token_hex(32)
        with open(CACHE_FILE, "w") as f:
            json.dump(settings, f, indent=2)

    return settings[key_type]

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
        with open(CACHE_FILE, "w") as f:
            json.dump({}, f)
        return {"zipcode": "67260", "country": "us", "units": "imperial", "ui_mode": "dark"}

# if the file does not exist, then make a new one, and paste in an empty dict,
# if the file does exist, then load settings from it to use later
settings = load_settings()
# define variables with data from settings
country = settings["country"]
zipcode = settings["zipcode"]
units = settings["units"]
ui_mode = settings["ui_mode"]

lat, lon = get_lat_lon(zipcode)
weather_api_key = get_keys("weather") 
weather_daily_url = f"http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={weather_api_key}&units={units}"
weather_forecast_url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&units={units}&appid={weather_api_key}"

blackboard_ics_url = get_keys("blackboard")
flask_session_id = get_keys("flask_session")

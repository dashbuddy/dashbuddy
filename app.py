from flask import Flask, request, redirect, render_template, flash
from PIL import Image, ImageDraw, ImageFont
from inky.auto import auto
from threading import Event
from icalendar import Calendar
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import os, requests, pykeys, time, textwrap

app = Flask(__name__)
app.secret_key = pykeys.flask_session_id
# Define paths for the folder for slideshows and the folder for single pictures
SLIDESHOW_FOLDER = '/home/pi/dashbuddy/uploads/slideshow'
PICTURES_FOLDER = '/home/pi/dashbuddy/uploads/pictures'
CALENDAR_FOLDER = '/home/pi/dashbuddy/uploads/calendar'
# sets display values needed for displaying stuff automagically,
# by reading from the EEPROM on the display
inky = auto()
display = auto()
WIDTH, HEIGHT = display.WIDTH, display.HEIGHT
# multithreading stuff
slideshow_running = Event()
# preset for ui is light mode (white (light mode) is 1, black (dark mode) is 0)
ui_color = 1
# make an instance of datetime as now
now = datetime.now(timezone.utc)
# colors = black:0, white:1, yellow:2, red:3
# make the background image so we can draw on it
img = Image.new("RGBA", (WIDTH, HEIGHT), ui_color)
draw = ImageDraw.Draw(img)
# collect the fonts to use later
font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
# define a list of colors for easy use later on
inky_colors = {
    "black": (0,0,0),
    "white": (255,255,255),
    "red": (255,0,0),
    "yellow": (255,255,0),
    "blue": (0,0,255),
    "green": (0,255,0),
    "fg": (255,255,255) if pykeys.ui_mode == "dark" else (0,0,0),
    "bg": (0,0,0) if pykeys.ui_mode == "dark" else (255,255,255)
}

# function to outline text that might not be visible due to background
# accepts: text (string), position (tuple), font (object), color (int), outline_color (int), outline_width (int)
def draw_outlined_text(text, position, font, color, outline_color, outline_width=1):
    x, y = position
    # draw outline
    for dx in range(-outline_width, outline_width + 1):
        for dy in range(-outline_width, outline_width + 1):
            if dx != 0 or dy != 0:
                # draw larger text in outline color
                draw.text((x + dx, y + dy), text, fill=outline_color, font=font)
    # draw normal sized text in fill color
    draw.text((x,y), text, fill=color, font=font)

def collect_next_days(num):
    today = now.date()
    next_days = [today + timedelta(days=i) for i in range(num)]
    return next_days

def check_ui():
    global img
    global draw
    # update inky_colors
    if pykeys.ui_mode == "dark":
        inky_colors["fg"] = (255,255,255)
        inky_colors["bg"] = (0,0,0)
    elif pykeys.ui_mode == "light":
        inky_colors["fg"] = (0,0,0)
        inky_colors["bg"] = (255,255,255)
    # update these instances so that the background can have the new ui_color
    img = Image.new("RGB", (WIDTH,HEIGHT), inky_colors["bg"])
    draw = ImageDraw.Draw(img)

def get_calendar(ics_text):
    # sort events into
    now = datetime.now(timezone.utc)
    upcoming = []
    # iterate through the calendar and find events
    for component in calendar.walk():
        if component.name == "VEVENT":
            start = component.get('dtstart').dt
            # check if start date has already passed, if not then add to list
            if isinstance(start, datetime) and start > now:
                upcoming.append(component)
    # Sort upcoming events and store in a list capped at 5
    upcoming = sorted(upcoming, key=lambda e: e.get('dtstart').dt)[:5]
    return upcoming

def display_calendar(ics):
    # sets ui color to correct value
    check_ui()
    # draw some headers onto the screen
    draw_outlined_text("Schedule", (10,10), font, color=inky_colors["yellow"], outline_color=inky_colors["black"], outline_width=3)
    draw.text((400,10), "Upcoming Events:", inky_colors["fg"], font=font)
    # get the dates for the next 5 days
    days = collect_next_days(5)
    # set sizing and placement constants
    box_width = WIDTH // 5
    box_height = HEIGHT // 2
    dot_y = 50
    dot_radius = 5
    try:
        # collects list of upcoming events from blackboard
        upcoming_list = get_calendar(ics)
        # draw the next 3 upcoming events to the top of the screen
        for idx, event in enumerate(upcoming_list[:3]):
            draw.text((400,35*(idx+2)), f"{event.get('dtstart').dt.date()} - {event.get('summary')}", inky_colors["fg"], font=small_font)  

        # iterate through the 5 days we gathered earlier and draw a box for each
        for idx, day in enumerate(days):
            col = idx % 5
            row = 1
            box_x = col * box_width
            box_y = row * box_height

            draw.rectangle([box_x, box_y, box_x + box_width, box_y + box_height], outline=inky_colors["fg"], width=3)
            draw.text((box_x + 4, box_y + 4), day.strftime("%b %d"), font=font, fill=inky_colors["fg"])
            # create a list of events happening on this day
            daily_events = [e for e in upcoming_list if e.get('dtstart').dt.date() == day]
            if not daily_events:
                return "No upcoming events found"
            cy = box_y + 40
            # iterate through the events on this day, limited at 2
            for i, event in enumerate(daily_events[:2]):
                title = str(event.get('summary'))
                date = event.get('dtstart').dt.strftime("%I:%M %p")
                text = f"<{date}> {title}"

                cx = box_x + 10
                # draw black outline for dot and then the colored dot on top
                draw.ellipse((cx - dot_radius+1, cy - dot_radius+1, cx + dot_radius+1, cy + dot_radius+1), fill=inky_colors["black"])
                draw.ellipse((cx - dot_radius, cy - dot_radius, cx + dot_radius, cy + dot_radius), fill=inky_colors["yellow"])

                wrapped = textwrap.wrap(text, width=10)
                for line in wrapped:
                    draw.text((cx + 2 * dot_radius + 4, cy - 10), line, inky_colors["fg"], font=small_font)
                    cy += 25
                cy += 5

        # tell the display to update and show stuff
        display.set_image(img)
        display.show()
        # if the program maade it this far, return "None" to indicate no error
        return None

    except Exception as e:
        return f"WARNING: ics file may be corrupt, outdated, missing, or empty"

def get_weather(type):
    # queries the weather api and parses data
    if type == "today":
        response = requests.get(pykeys.weather_daily_url)
        data = response.json()
    elif type == "forecast":
        response = requests.get(pykeys.weather_forecast_url)
        data = response.json()
    return data

def summarize_forecast(forecast_data):
    days_summary = []

    grouped = defaultdict(list)
    for entry in forecast_data.get("list", []):
        dt = datetime.fromtimestamp(entry["dt"])
        date_str = dt.strftime("%Y-%m-%d")
        grouped[date_str].append(entry)

    for date, entries in grouped.items():
        temps = [e["main"]["temp"] for e in entries]
        conditions = [e["weather"][0]["main"] for e in entries]
        avg_condition = max(set(conditions), key=conditions.count)

        summary = {
            date: {
                "temp_min": min(temps),
                "temp_max": max(temps),
                "condition": avg_condition,
                "icon": entries[0]["weather"][0]["icon"]
            }
        }
        days_summary.append(summary)

    return days_summary

def display_weather():
    # sets the ui color to the correct value
    check_ui()
    # collect weather data from openWeatherMap.org
    weather = get_weather("today")

    # parse data for the weather data gathering we did earlier
    weather_main = weather["weather"][0]["main"].lower()
    description = weather["weather"][0]["description"].capitalize()
    icon_path = f"static/icons/{weather_main}.png"
    temp = round(weather["main"]["temp"])
    feels_like = round(weather["main"]["feels_like"])
    humidity = weather["main"]["humidity"]
    wind_speed = round(weather["wind"]["speed"])

    # start to draw text onto screen for todays weather
    text_color = inky_colors["fg"]
    draw.text((10,20), f"{description}", font=font, fill=text_color)
    draw.text((10,50), f"Temp: {temp}°F (feels like {feels_like}°F)", font=font, fill=text_color)
    draw.text((10,80), f"Humidity: {humidity}%", font=font, fill=text_color)
    draw.text((10,110), f"Wind: {wind_speed} mph", font=font, fill=text_color)
    # draw icons
    icon = Image.open(icon_path).convert("RGBA")
    img.paste(icon, (550, 75), icon)

    # get the weather once more, this time for forecasts
    weather = get_weather("forecast")
    # do some funky magic to get averages for weather data,
    # since forecast returns the day in 3 hour chunks
    daily_data = summarize_forecast(weather)
    days_list = []
    days = collect_next_days(4)
    for day in days:
        days_list.append(day.strftime("%Y-%m-%d"))

    BOX_WIDTH = WIDTH // 3
    BOX_HEIGHT = HEIGHT // 2
    box_num = 0
    for idx, info in enumerate(daily_data):
        if box_num > 2:
            break
        col = box_num % 3
        row = 1
        box_x = col * BOX_WIDTH
        box_y = row * BOX_HEIGHT
        box_num += 1

        temp_max = round(info[days_list[idx]]["temp_max"])
        temp_min = round(info[days_list[idx]]["temp_min"])
        condition = info[days_list[idx]]["condition"]

        draw.rectangle([box_x, box_y, box_x + BOX_WIDTH, box_y + BOX_HEIGHT], outline=inky_colors["fg"], width=3)
        draw.text((box_x + 4, box_y + 4), days_list[idx+1], font=font, fill=inky_colors["fg"])
        draw.text((box_x + 4, box_y + 34), f"Max Temperature:{temp_max}°F", font=small_font, fill=inky_colors["fg"])
        draw.text((box_x + 4, box_y + 54), f"Min Temperature:{temp_min}°F", font=small_font, fill=inky_colors["fg"])
        icon_path = f"static/icons/{condition.lower()}.png"

        try:
            icon = Image.open(icon_path).convert("RGBA")
            img.paste(icon, (box_x + 50, box_y + 84), icon)
        except:
            print(f"couldnt paste image for {condition}")

    # actually tells the display to show stuff
    display.set_image(img)
    display.show()

'''
def run_slideshow(delay=120):
    slideshow_running.set()
    while slideshow_running.is_set():
        images = sorted([
            os.path.join(UPLOAD_FOLDER, f)
            for f in os.listdir(UPLOAD_FOLDER)
            if f.lower().endswith((".png", ".jpg", ".jpg"))
        ])
        if not images:
            break
        for image_path in images:
            if not slideshow_running.is_set():
                return
            img = Image.open(image_path).resize(display.resolution)
            display.set_image(img)
            display.show()
            time.sleep(delay)

@app.route("/clear_slideshow", methods=["POST"])
def clear_slideshow():
    for filename in os.listdir(UPLOAD_FOLDER):
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        if os.path.isfile(file_path):
            os.remove(file_path)
        return render_template("index.html")

@app.route("/stop_slideshow", methods=["POST"])
def stop_slideshow():
    slideshow_running.clear()

@app.route("/start_slideshow", methods=["POST"])
def start_slideshow():
    import threading
    threading.Thread(target=run_slideshow, daemon=True).start()
    return render_template("index.html")

@app.route("/upload_slideshow", methods=["POST"])
def upload_slideshow():
    files = request.files.getlist("images")
    for file in files:
        if file and file.filename:
            path = os.path.join(UPLOAD_FOLDER, file.filename)
            with open(path, "wb") as f:
                f.write(file.read())
    return render_template("index.html")
'''





@app.route('/save-settings', methods=["POST"])
def save_settings():
    pykeys.save_setting("ui_mode", request.form.get("ui_mode"))
    pykeys.save_setting("units", request.form.get("units"))
    pykeys.save_setting("country", request.form.get("country"))
    pykeys.save_setting("zipcode", request.form.get("zipcode"))
    return redirect("/")

@app.route('/upload-image', methods=["POST"])
def update_image():
    file = request.files["image"]
    if file:
        path = os.path.join(PICTURES_FOLDER, "latest.png")
        file.save(path)

        #resize and show on display
        img = Image.open(path).convert("RGB")
        img = img.resize(display.resolution)
        inky.set_image(img)
        inky.show()

        return redirect("/")

@app.route('/calendar', methods=["POST"])
def update_calendar():
    calendar_url = request.form.get("calendar_url")
    calendar_file = request.files.get("calendar_file")
    status_message = None

    # handle ics from url
    if calendar_url:
        try:
            ics_data = requests.get(calendar_url).text
            status_message = display_calendar(ics_data)
        except Exception as e:
            status_message = f"Failed to fetch calendar: {e}"
    # handle ics from file upload
    elif calendar_file and calendar_file.filename != "":
        path = os.path.join(CALENDAR_FOLDER, "latest.ics")
        calendar_file.save(path)
        calendar_file.stream.seek(0)
        ics_data = calendar_file.read().decode("utf-8")
        status_message = display_calendar(ics_data)

    if status_message:
        flash(status_message, category="warning")

    return redirect("/")

@app.route('/weather', methods=['POST'])
def update_weather():
    display_weather()
    return redirect("/")

@app.route("/", methods=["GET", "POST"])
def home():
    settings = pykeys.load_settings()
    return render_template("index.html", settings=settings)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)


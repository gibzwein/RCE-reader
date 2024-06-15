import network
import time
import credentials
import ssd1306
import urequests as requests
import machine, neopixel
import utime
import ntptime

# import wifimgr
# from time import sleep
# import machine

# try:
#   import usocket as socket
# except:
#   import socket

from machine import Pin, SoftI2C

last_hour_change = 0

# Move to credentials.py > import to main > done!
ssid = credentials.ssid
password = credentials.password

# WiFi config
sta = network.WLAN(network.STA_IF)
print(sta.ifconfig())

# LED Config
led_pin = 2 
led = machine.Pin(led_pin, machine.Pin.OUT)

# LCD/OLED config
i2c = SoftI2C(scl=Pin(22), sda=Pin(21))
oled_width = 128
oled_height = 64

i2c_devices = i2c.scan()
print(i2c_devices)
if len(i2c_devices) != 0:
    oled = ssd1306.SSD1306_I2C(oled_width, oled_height, i2c)

# Configuration for timezone and daylight saving
TIMEZONE_OFFSET = 1  # Offset in hours from UTC (standard time)
DAYLIGHT_SAVING_OFFSET = 1  # Additional offset during daylight saving time

def is_daylight_saving():
    # Implement a method to determine if daylight saving time is in effect
    # For simplicity, assume daylight saving time is in effect from the last Sunday in March to the last Sunday in October
    current_date = utime.localtime()
    year = current_date[0]
    month = current_date[1]
    day = current_date[2]
    weekday = current_date[6]

    if month < 3 or month > 10:
        return False
    if month > 3 and month < 10:
        return True
    
    # Calculate last Sunday of March
    last_sunday_march = 31 - (utime.mktime((year, 3, 31, 0, 0, 0, 0, 0)) // 86400 + 3) % 7
    # Calculate last Sunday of October
    last_sunday_october = 31 - (utime.mktime((year, 10, 31, 0, 0, 0, 0, 0)) // 86400 + 3) % 7

    if month == 3 and day > last_sunday_march:
        return True
    if month == 10 and day <= last_sunday_october:
        return False
    if month == 3 and day <= last_sunday_march:
        return False
    if month == 10 and day > last_sunday_october:
        return True

    return False

def get_local_time():
    current_time = utime.time()
    local_time = current_time + TIMEZONE_OFFSET * 3600
    if is_daylight_saving():
        local_time += DAYLIGHT_SAVING_OFFSET * 3600
    return utime.localtime(local_time)

# wlan = wifimgr.get_connection()
# if wlan is None:
#     print("Could not initialize the network connection.")
#     while True:
#         pass  # you shall not pass :D

# # Main Code goes here, wlan is a working network.WLAN(STA_IF) instance.
# print("ESP OK")

def wifi_connect():
    try:
        print("Connecting to WiFi", end="")
        sta.active(True)
        time.sleep(1)
        sta.connect(ssid, password)
        oled.fill(0)
        oled.text('Connecting WiFi', 0, 0)
        oled.show()
        timeout = 20  # Zwiększenie czasu oczekiwania na połączenie
        while not sta.isconnected() and timeout > 0:
            print(".", end="")
            time.sleep(0.5)
            timeout -= 1
        if sta.isconnected():
            print("\nWiFi Connected!")
            ntptime.settime()
            oled.fill(0)
            oled.text('WiFi Connected', 0, 0)
            oled.show()
            time.sleep(1)
            full_loop()
        else:
            print("\nFailed to connect to WiFi.")
            oled.fill(0)
            oled.text('WiFi Failed', 0, 0)
            oled.show()
            time.sleep(1)
            wifi_connect()
    except OSError as e:
        print(f"\nOSError: {e}")
        oled.fill(0)
        oled.text('WiFi Error', 0, 0)
        oled.show()
        time.sleep(5)
        sta.active(False)
        time.sleep(1)
        wifi_connect()

def get_current_hour():
    local_time = get_local_time()
    formatted_hour = local_time[3]
    print('Current hour:', formatted_hour)
    return formatted_hour

def get_current_date():
    local_time = get_local_time()
    formatted_date = f"{local_time[0]:04}{local_time[1]:02}{local_time[2]:02}"
    print('Current date:', formatted_date)
    return formatted_date

def get_data():
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            date = get_current_date()
            url = f"https://www.pse.pl/getcsv/-/export/csv/PL_CENY_RYN_EN/data/{date}"
            print("Requesting URL:", url)
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                return response.text
            else:
                print(f"Error while retrieving data. Response code: {response.status_code}")
                retry_count += 1
                if retry_count < max_retries:
                    print(f"Retrying to fetch data in {5 * retry_count} seconds...")
                    time.sleep(5 * retry_count)
                else:
                    print("Exceeded maximum number of data retrieval attempts.")
                    return None
        except Exception as e:
            print(f"An error occurred while retrieving data: {e}")
            retry_count += 1
            if retry_count < max_retries:
                print(f"Retrying to fetch data in {5 * retry_count} seconds...")
                time.sleep(5 * retry_count)
            else:
                print("Exceeded maximum number of data retrieval attempts.")
                return None
            
def parse_data(data):
    parsed_data = []
    for line in data.split('\n')[1:]:
        if line:
            values = line.strip().split(';')
            date = values[0]
            hour = int(values[1])
            price = float(values[2].replace(',', '.'))
            entry = {'date': date, 'hour': hour, 'price': price}
            parsed_data.append(entry)
    return parsed_data

def calculate_average(data):
    total = sum(entry['price'] for entry in data)
    min_price = min(entry['price'] for entry in data)
    max_price = max(entry['price'] for entry in data)
    return {'average': total / len(data), 'min': min_price, 'max': max_price}

def get_data_for_hour(data, hour):
    for entry in data:
        if entry['hour'] == hour + 1:  # 22:00 -> 22:59 is 22 hour
            return entry
    return None

def display_data(price_data, price):
    np = neopixel.NeoPixel(machine.Pin(15), 1)
    print(f"Current price: {price}")
    oled.fill_rect(0, 0, 128, 8, 0)
    oled.text(f"RCEg: {price}", 0, 0)
    oled.show()
    range_price = price_data['max'] - price_data['min']
    low = price_data['min'] + range_price * 0.33
    high = price_data['min'] + range_price * 0.66
    if price < 0:
        np[0] = (0, 0, 255)  # Blue
        print("Price lower than 0")
        oled.text('B', 119, 0)
    elif price < low:
        np[0] = (0, 255, 0)  # Green
        print("Green")
        oled.text('G', 119, 0)
    elif price < high:
        np[0] = (255, 255, 0)  # Yellow
        print("Yellow")
        oled.text('Y', 119, 0)
    else:
        np[0] = (255, 0, 0)  # Red
        print("Red")
        oled.text('R', 119, 0)
    np.write()
    oled.show()

def full_loop():
    try:
        current_hour = get_current_hour()
        oled.fill(0)
        oled.text('Fetching data', 0, 0)
        oled.show()
        data = get_data()
        if data is None:
            print("Error to retrieve data.")
            oled.fill(0)
            oled.text('No data from PSE', 0, 0)
            oled.show()
            time.sleep(1)
            return
        parsed_data = parse_data(data)
        if not parsed_data:
            print("Error parsing data.")
            return
        average_data = calculate_average(parsed_data)
        hour_data = get_data_for_hour(parsed_data, current_hour)
        if hour_data:
            display_data(average_data, hour_data['price'])
        else:
            print("No data for current hour.")
    except RuntimeError as e:
        print(f"Error in full_loop: {e}")

current_hour = 0

def check_hour_change():
    global last_hour_change
    global current_hour
    last_hour_change = time.time()
    hour = get_local_time()[3]
    if hour != current_hour:
        current_hour = hour
        print(f"Hour changed: {current_hour}")
        full_loop()
    else:
        print("Hour not changed")
        
while True:
    if not sta.isconnected():
        wifi_connect()
    if time.time() - last_hour_change > 60:
        check_hour_change()

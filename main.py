import gc
import micropython
from  machine import Pin, RTC
import network
from ntptime import settime
import time
import _thread
from secrets import secrets
import uasyncio as asyncio
from ota import OTAUpdater

# Global values
gc_text = ''
DATAFILENAME = 'data.txt'
LOGFILENAME = 'log.txt'
ERRORLOGFILENAME = 'errorlog.txt'
ssid = secrets['ssid']
password = secrets['wifi_password']
TZ_OFFSET = secrets['tz_offset']

# Set up DST pin
# Jumper to ground when DST is in effect
DST_pin = Pin(17, Pin.IN, Pin.PULL_UP)

# Account for Daylight Savings Time
if DST_pin.value():
    tz_offset = TZ_OFFSET
else:
    tz_offset = TZ_OFFSET + 1

# Set up onboard led
onboard = Pin("LED", Pin.OUT, value=0)

html = """<!DOCTYPE html>
<html>
    <head> <title>Re-Connect on Power Failure</title> </head>
    <body> <h1>Re-Connect</h1>
        <h3>%s</h3>
        <pre>%s</pre>
    </body>
</html>
"""

def sync_rtc_to_ntp():
    """Sync RTC to (utc) time from ntp server."""
    try:
        settime()
    except OSError as e:
        with open(ERRORLOGFILENAME, 'a') as file:
            file.write(f"OSError while trying to set time: {str(e)}\n")
    print('setting rtc to UTC...')

def local_hour_to_utc_hour(loc_h):
    utc_h = loc_h - tz_offset
    if utc_h > 23:
        utc_h -= 24
    return utc_h

def utc_hour_to_local_hour(utc_h):
    loc_h = utc_h + tz_offset
    if loc_h < 0:
        loc_h += 24
    return loc_h

def record(line):
    """Combined print and append to data file."""
    print(line)
    line += '\n'
    with open(DATAFILENAME, 'a') as file:
        file.write(line)

wlan = network.WLAN(network.STA_IF)

def connect():
    """Return True on successful connection, otherwise False"""
    wlan.active(True)
    wlan.config(pm = 0xa11140) # Disable power-save mode
    wlan.connect(ssid, password)

    max_wait = 10
    while max_wait > 0:
        if wlan.status() < 0 or wlan.status() >= 3:
            print("wlan.status =", wlan.status())
            break
        max_wait -= 1
        print('waiting for connection...')
        time.sleep(1)

    if not wlan.isconnected():
        return False
    else:
        print('connected')
        status = wlan.ifconfig()
        print('ip = ' + status[0])
        return True

async def serve_client(reader, writer):
    try:
        print("Client connected")
        request_line = await reader.readline()
        print("Request:", request_line)
        # We are not interested in HTTP request headers, skip them
        while await reader.readline() != b"\r\n":
            pass

        if '/log' in request_line.split()[1]:
            with open(LOGFILENAME) as file:
                data = file.read()
            heading = "Occurences"
        elif '/err' in request_line.split()[1]:
            with open(ERRORLOGFILENAME) as file:
                data = file.read()
            heading = "ERRORS"
        else:
            with open(DATAFILENAME) as file:
                data = file.read()
            heading = "Append '/log' or '/err' to URL to see log file or error log"

        data += gc_text

        response = html % (heading, data)
        writer.write('HTTP/1.0 200 OK\r\nContent-type: text/html\r\n\r\n')
        writer.write(response)

        await writer.drain()
        await writer.wait_closed()
        print("Client disconnected")
    except Exception as e:
        with open(ERRORLOGFILENAME, 'a') as file:
            file.write(f"serve_client error: {str(e)}\n")

async def main():
    global gc_text, tz_offset
    print('Connecting to Network...')
    connect()

    # Check for OTA updates
    repo_name = "pico-OTA"
    branch = "main"
    firmware_url = f"https://github.com/dblanding/{repo_name}/{branch}/"
    ota_updater = OTAUpdater(firmware_url, "main.py", "ota.py")
    ota_updater.download_and_install_update_if_available()

    # Pico Real Time Clock
    rtc = RTC()
    local_time = rtc.datetime()
    print("Initial (rtc) ", local_time)

    # Sync RTC to ntp time server (utc)
    sync_rtc_to_ntp()
    time.sleep(1)

    gm_time = rtc.datetime()
    print('Reset to (UTC)', gm_time)
    record("power-up @ (%d, %d, %d, %d, %d, %d, %d, %d) (UTC)" % gm_time)

    print('Setting up webserver...')
    asyncio.create_task(asyncio.start_server(serve_client, "0.0.0.0", 80))
    while True:

        # Check for daylight savings time (set w/ jumper)
        if DST_pin.value():
            tz_offset = TZ_OFFSET
        else:
            tz_offset = TZ_OFFSET + 1

        try:
            current_time = rtc.datetime()
            y = current_time[0]  # curr year
            mo = current_time[1] # current month
            d = current_time[2]  # current day
            h = current_time[4]  # curr hour (UTC)
            lh = utc_hour_to_local_hour(h) # (local)
            m = current_time[5]  # curr minute
            s = current_time[6]  # curr second
            
            timestamp = f"{lh:02}:{m:02}:{s:02}"

            # Test WiFi connection twice per minute
            if s in (15, 45):
                if not wlan.isconnected():
                    record(f"{timestamp} WiFi not connected")
                    wlan.disconnect()
                    record("Attempting to re-connect")
                    success = connect()
                    record(f"Re-connected: {success}")
                    # After successful reconnection, sync rtc to ntp
                    if success:
                        sync_rtc_to_ntp()
                        time.sleep(1)
            
            # Print time on 30 min intervals
            if s in (1,) and not m % 30:
                try:
                    record(f"datapoint @ {timestamp}")
                    
                    gc_text = f"free: {str(gc.mem_free())}\n"
                    gc.collect()
                except Exception as e:
                    with open(ERRORLOGFILENAME, 'a') as file:
                        file.write(f"error printing: {repr(e)}\n")

            # Once daily (during the wee hours)
            if lh == 2 and m == 10 and s == 1:
                
                # Read lines from previous day
                with open(DATAFILENAME) as f:
                    lines = f.readlines()

                # first line is yesterday's date
                yesterdate = lines[0].split()[-1].strip()

                # cull all lines containing '@'
                lines = [line
                         for line in lines
                         if '@' not in line]
                
                # Log lines from previous day
                with open(LOGFILENAME, 'a') as f:
                    for line in lines:
                        f.write(line)
                
                # Start a new data file for today
                with open(DATAFILENAME, 'w') as file:
                    file.write('Date: %d/%d/%d\n' % (mo, d, y))

        except Exception as e:
            with open(ERRORLOGFILENAME, 'a') as file:
                file.write(f"main loop error: {str(e)}\n")

        # Flash LED
        onboard.on()
        await asyncio.sleep(0.1)
        onboard.off()
        await asyncio.sleep(0.9)

try:
    asyncio.run(main())
finally:
    asyncio.new_event_loop()

# test.py

import urequests
import json

base_url = "https://raw.githubusercontent.com/dblanding/pico-OTA/"
branch = "main/"
path_to_file = "micropython_scripts/reconnect_on_pf/version.json"
version_url = base_url + branch + path_to_file
response = urequests.get(version_url)
print(response.text)
data = json.loads(response.text)
print(f"data version is: {data['version']}")

# OTA Updater for micropython running on a Pico W

* Based on Kevin McAleer's [MicroPython Over-the-Air updater](https://github.com/kevinmcaleer/ota) modified as follows:
    * The WiFi connection is made outside of OTAUpdater
    * Allows multiple files to be specified for updating, 
using this syntax:
``` python
    # Check for OTA updates
    firmware_url = f"https://github.com/{GitHub_username}/{repo_name}/{branch}/"
    ota_updater = OTAUpdater(firmware_url, <filename1>, <filename2>, ...)
    ota_updater.download_and_install_update_if_available()
```


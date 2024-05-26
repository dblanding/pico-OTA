# OTA Updater for micropython running on a Pico W

* Based on Kevin McAleer's [MicroPython Over-the-Air updater](https://github.com/kevinmcaleer/ota) modified as follows:
    * Allows multiple files to be specified for updating
    * The caller injects the name of the branch (usually `main`)
    * The WiFi connection is made outside of OTAUpdater


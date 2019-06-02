# This test shows how to use wifi_setup

# These two lines make sure that there is a configured wifi that is connected.
# If there is no wifi.json saved yet, or if there is no wifi that can be
# connected with the saved parameters, then the device goes into AP mode
# and you can use http://192.168.4.1 to setup a new wifi connection.
import esp
import wifi_setup
import utime

esp.osdebug(None)
wifi_setup.DEBUG = True

def on_reset_config():
    # You may want to indicate this with turning on all leds!
    print("Configuration has been hard-reset!")

if wifi_setup.main(on_reset_config=on_reset_config, reset_pin=14):
    print("wifi_setup complete, starting main program")
    import run
else:
    print("Escaped to prompt!")


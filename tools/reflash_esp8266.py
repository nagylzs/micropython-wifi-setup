import os
import sys

sys.path.insert(0, os.environ["MP_HOME"])
from mp_tools import *

esptool("erase_flash")
esptool("--baud 115200 write_flash --flash_size=detect 0 %s" % LATEST_ESP8266_FIRMWARE_PATH)

print("""

HARD RESET IS REQUIRED AFTER REFLASHING.

This is not a joke! Invoking machine.reset() or calling
"syncer reset" won't suffice. If you have a dev board, you can press
the hardware reset button. If you don't have a hw reset button, then
power off and power on the device.

PRESS ENTER WHEN YOU ARE READY.

""")
input("")

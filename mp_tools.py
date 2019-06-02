import os
import sys
import subprocess

MP_HOME = os.path.split(os.path.abspath(__file__))[0]
MP_TOOLS = os.path.join(MP_HOME, "tools")
MP_LIBS = os.path.join(MP_HOME, "libs")
MP_ASSETS = os.path.join(MP_HOME, "assets")
MP_FIRMWARES = os.path.join(MP_HOME, "firmwares")


def get_firmwares(code_name):
    return [fname for fname in sorted(os.listdir(
        os.path.join(MP_FIRMWARES, code_name))) if fname.lower().endswith(".bin")]


ESP8266_FIRMWARES = get_firmwares("esp8266")
LATEST_ESP8266_FIRMARE = ESP8266_FIRMWARES[-1]
LATEST_ESP8266_FIRMWARE_PATH = os.path.join(MP_FIRMWARES, "esp8266", LATEST_ESP8266_FIRMARE)

ESP32_FIRMWARES = get_firmwares("esp32")
LATEST_ESP32_FIRMWARE = ESP32_FIRMWARES[-1]
LATEST_ESP32_FIRMWARE_PATH = os.path.join(MP_FIRMWARES, "esp32", LATEST_ESP32_FIRMWARE)

ESP_SYNC = os.path.join(MP_TOOLS, "espsyncer.py")
ESP_SYNC_CMD = "%s %s -v " % (sys.executable, ESP_SYNC)

ESP_PORT = os.environ["ESP_PORT"]
ESP_TOOL_CMD = "esptool.py --port %s" % ESP_PORT

ESP_MINIFY_CMD = "%s %s/esp_minify_www.py" % (sys.executable, MP_TOOLS)


def run(cmd):
    print("RUN: ", cmd)
    subprocess.run(cmd, shell=True, check=True)


def sync(args_str):
    run(ESP_SYNC_CMD + " " + args_str)


def esptool(args_str):
    run(ESP_TOOL_CMD + " " + args_str)


def minify(args_str):
    run(ESP_MINIFY_CMD + " " + args_str)

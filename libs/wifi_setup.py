import os
import socket
import select
import network
import gc
import json
import websrv
import utime
import machine

RESET_TIME = 5
DEBUG = False

try:
    with open("wifi_ap.json", "r") as fin:
        ap_params = json.loads(fin.read())
except:
    ap_params = dict(essid='wifi_setup', channel=1, authmode=3, password='abcd1234', hidden=False)
    if DEBUG:
        print("wifi_ap.json not found, using", ap_params)

ap = network.WLAN(network.AP_IF)
ap.active(True)
if DEBUG:
    print(ap_params)
ap.config(**ap_params)

wlan = network.WLAN(network.STA_IF)
wlan.active(True)

gc.collect()

NOP = False

wifi_params = {}
wifi_params_good = {}
try:
    with open("wifi.json", "r") as fin:
        wifi_params = json.loads(fin.read())
    wifi_params_orig = json.loads(json.dumps(wifi_params))
    if DEBUG:
        print("wifi.json loaded")
        print(wifi_params_orig)
except:
    if DEBUG:
        print("wifi.json not available")


def save_params():
    if NOP and DEBUG:
        print("wifi.json NOT SAVED (nop)")
        return
    with open("wifi.json", "w+") as fout:
        fout.write(json.dumps(wifi_params_good))
    if DEBUG:
        print("wifi.json saved")
        print(wifi_params_good)


ssid = None

gc.collect()


# Example web service program
def handle(cl, addr, args):
    global ssid
    if DEBUG:
        print(args)
    op = args["op"]
    if op == "scan_wifi":
        return wlan.scan()
    elif op == "get_wifi_params":
        return wifi_params
    elif op == "set_wifi_param":
        params = args["params"]
        wifi_params[params["ssid"]] = params
        return True
    elif op == "connect_configured_wifi":
        ssid = args["ssid"]
        params = wifi_params[ssid]
        wlan.connect(ssid, params["password"])
    elif op == "ap_status":
        return wlan.status()
    elif op == "ifconfig":
        if wlan.isconnected():
            cfg = wlan.ifconfig()
            if cfg and ssid in wifi_params:
                wifi_params[ssid]["last_ifconfig"] = cfg
                wifi_params_good[ssid] = wifi_params[ssid]
                save_params()
            return cfg
        else:
            return None
    elif op == "reset":
        machine.reset()
    else:
        raise Exception("Invalid operation")


def run_setup(webroot='/www/wifi_setup'):
    addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
    srv = socket.socket()
    srv.bind(addr)
    srv.listen(10)

    poll = select.poll()
    poll.register(srv, select.POLLIN)
    while True:
        res = poll.poll(50)  # Is there something to read?
        if len(res):
            item, event = res[0]
            if item is srv:
                try:
                    websrv.serve_get(srv, handle, webroot=webroot)
                except OSError:
                    pass  # ECONNRESET?
            # else ....
            #
        else:
            gc.collect()


def try_net(ssid):
    wlan.connect(ssid, wifi_params[ssid]["password"])
    while True:
        st = wlan.status()
        if st == network.STAT_CONNECTING:
            utime.sleep(0.2)
        elif st == network.STAT_GOT_IP:
            return True
        else:
            return False


def main(webroot='/www/wifi_setup', reset_pin=14, on_reset_config=None):
    configured = True
    try:
        os.stat('wifi.json')
    except:
        configured = False
    if configured and reset_pin:
        if DEBUG:
            print("#1 init")
        pin = machine.Pin(reset_pin, machine.Pin.IN, machine.Pin.PULL_UP)
        if not pin.value():
            if DEBUG:
                print("#2 waiting to release button")
            elapsed = 0.0
            while not pin.value():
                utime.sleep(0.5)
                elapsed += 0.5
                if elapsed > RESET_TIME:
                    if DEBUG:
                        print("#3 pressed for %s seconds, should reset config here" % RESET_TIME)
                    try:
                        os.remove('wifi.json')
                    except:
                        pass
                    if on_reset_config:
                        try:
                            on_reset_config()
                        except:
                            if DEBUG:
                                print("#4 on_reset_config - exception!")
                    while not pin.value():
                        utime.sleep(0.5)
                    machine.reset()
            if DEBUG:
                print("#4 pressed for less than %s seconds, should escape to REPL here" % RESET_TIME)
                utime.sleep(1)
            return False
    # This returns ONLY if a network can be connected
    if wlan.active() and wlan.status() == network.STAT_GOT_IP:
        return True
    if not wifi_params:
        run_setup(webroot)  # never returns
    networks = wlan.scan()
    networks.sort(key=lambda item: -item[3])
    for n in networks:
        ssid = n[0].decode("ascii")
        if ssid in wifi_params:
            if try_net(ssid):
                return True
    run_setup(webroot)  # never returns

# micropython-wifi-setup

Automated Wifi setup backend and frontend code for MicroPyton and ESP8266/ESP32

## Installation steps

In this example, we are going to assume that you have cloned this project under `C:\Python\Projects\micropython-wifi-setup` on Windows. Please note that you MUST have administrator rights to open a COM port, so most of the commands below MUST be executed as aministrator.

It also does work under linux, but I did not write documentation for that yet.

* Download and install python 3.7 https://www.python.org/downloads/windows/
* Download and install node js LTS https://nodejs.org/en/download/
* Install yarn as administrator:

      npm install -g yarn

* Set your environment variables. ESP_PORT should be the port where your ESP is connected to.

      ESP_PORT=COM6 
      MP_HOME=C:\Python\Projects\micropython-wifi-setup
      HOST=0.0.0.0

 Also, add your micropython-wifi-setup/tools directory to your PATH e.g.

    PATH=c:\Python\Projects\micropython-wifi-setup\tools

* Do this as administrator on windows:

      python -m pip install pip --upgrade
      python -m pip install pipenv
      pip3 install pyserial
      pip3 install colorterm
      pip3 install esptool

* Burn a fresh firmare on your ESP, if you haven't done so. Run this as administrator, depending on your chip:

      reflash_esp8266.py
      
   OR
   
      reflash_esp32.py

 * Build the frontend - Run this as administrator

       cd c:\Python\Projects\micropython-wifi-setup\assets\wifi_setup
       01_build.py

This will first "yarn run build" into the assets\wifi_setup\build directory, then minify the code into assets\wifi_setup\wifi_setup - this minified code will also take care of the TCP queue size problem with MicroPython on ESP8266.

* Deploy all libraries and also the minfied wifi_setup frontend code to the device.

      02_deploy.py

The first upload will take a while. Subsequent uploads will only upload the files that are changed.

## How to test on the ESP

If you want to try this code, then please install the test backend. It is located here: `micropython-wifi-setup\assets\wifi_setup\test_backend`.  The test backend implements a "Hello world" web server on port 80. The test backend can be installed by invoking `03_deploy_test.py` in that directory.

Please note that the test backend will NOT start automatically. You will have to connect to your ESP with a serial terminal, and invoke `import test` in order to start the test backend. When you finished testing, then you can rename `test.py` to `main.py` and it will start automatically.

When the test backend starts, you will see a new Wifi network called `wifi_setup`. Connect to it (default password: abcd1234) Then open http://192.168.4.1 with your browser, and you should see the web interface where you can setup your wifi parameters. After you have successfully connected to a network, please write down your new client IP and press the "Finish (reboot)" button to restart your ESP device. At this point, please keep in mind that you have to do `import test` to continue the process on the ESP! Finally, point your browser to the new client IP and you should see `Hello World`.
 

## How it works (API)

In general, your main.py file should look like this:

    import wifi_setup
    #wifi_setup.DEBUG = True
    if wifi_setup.main(reset_pin=14):
        print("wifi_setup complete, starting main program")
        import run
    else:
        print("Escaped to prompt!")

The wifi_setup.main() function above does four possible things:

1. Reset function - If you pass a reset_pin argument value, and it reads 0, then it waits until it goes high (1). If this happens within 5 seconds, then it returns False. This feature can be used to escape to
REPL prompt (or do an alternative startup). This is useful for testing the device (because once you have this in your main.py, then you don't have any other way of escaping to a prompt, except re-flashing the whole device again). If the reset_pin is kept low for more than 5 seconds, then first it deletes the wifi.json file (wifi settings are stored there), then it calls back the on_reset_config callback (if given), finally if waits until the reset_pin goes high and calls machine.reset(). In other words: by keeping the
reset_pin low for more than 5 seconds, you make your device forget about all previously stored wifi networks ("factory reset"). The default reset_pin is GPIO14 (D5). If you pass zero, then it simply turns off the reset function. (It also means that you cannot escape to prompt or reset, only re-flash from scratch.) Be aware, not all pins can be kept low when the device start up. Consult ESP documentation.
1. Normal operation - connect to network. If the device is already connected to a network in client mode, then it returns True immediately. If it can connect to a (previously saved) network, then it connects and returns True. This is the "normal" operation. It may take a while to try out all configured networks.
1. Setup mode - In all other cases (no network is configured, or there are networks configured but they cannot be connected), the wifi_setup() function does not return at all. It starts a web server on 192.168.4.1 instead (in access point mode), and you can list available networks and configure them. The default AP network is:

       dict(essid='wifi_setup', channel=1, authmode=3, password='abcd1234', hidden=False)
       
  You can override this by placing a wifi_ap.json file on the device.

The rules above guarantee that an empty, never configured device will start the wifi setup service. Afer the first successful configuration, the configured network will be connected and your run.py module will be imported/started.

If you move the device to a different location with unknown networks, then it will automatically enter wifi_setup mode (after reset).

And finally, if you put a switch on the reset_pin (active low) then you will be able to clear all saved networks (hard reset) by holding down the swtich for more than 5 seconds while powering up the device.

## Making your own frontend

If you wish to alter the frontend, or creat your own, then open the frontend directory from Visual Studio code, and add your proxy to package.json. The idea is that you only upload the backend code to the device, and run the frontend on your own computer. This way you can quickly recompile and test your frontend without uploading (which is really slow).

If you also wish to try your frontend from a mobile device, then start your code this way:

    setx HOST 0.0.0.0
    yarn start

It will instruct webpack server to listen on all addresses, and then you will be able to connect to your webpack server from your mobile phone. Don't forget to open port 3000 on your firewall.

## Detailed settings

### AP settings 

To change default AP settings, you need to create and upload a wifi_ap.json file to the root of the device:

    {
    "essid": "wifi_setup",
    "channel":1,
    "authmode":3,
    "password":"abcd1234",
    "hidden":false
    }

Possible auth modes:

    enum WifiAuthMode {
      OPEN = 0,
      WEP = 1,
      WPA_PSK = 2,
      WPA2_PSK = 3,
      WPA_WPA2_PSK = 4
    }
    const WIFI_AUTH_MODE_NAMES: string[] = ["Open", "WEP", "WPA PSK", "WPA2 PSK", "WPA/WPA2 PSK"];


### Storage of configured networks  

Every successful configuration overwrites the /wifi.json file on the device. You cannot create these files by hand, because it also contains the last known client IP address. It is not possible to tell that address in advance.  

### Hard reset callback

The wifi_setup.main function has an on_reset_config callback parameter. It is called back after the user has kept the reset_pin low for more than 5 seconds. This can be used to notify the user about the hard reset.(For example: light up all LED-s.) When the callback returns, thenthe device will wait until the reset_pin goes high, and the resethappens only afterwards. It is also the case when the on_reset_config 
raises an exception.

 
## Known problems

The frontend speaks Hungarian right now. My apologies, I'm going to translate it when I'll have more time. It would be possible (and even better) to make it multilingual. PRs welcome.




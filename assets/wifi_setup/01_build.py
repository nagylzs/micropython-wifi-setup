import os
import sys
import shutil

sys.path.insert(0, os.environ["MP_HOME"])
from mp_tools import *

MYDIR = os.path.split(os.path.abspath(__file__))[0]
FRONTEND_DIR = os.path.join(MYDIR, "frontend")
os.chdir(FRONTEND_DIR)
yarn = shutil.which("yarn")
run([yarn, "install"])
run([yarn, "build"])
if os.path.isdir("wifi_setup"):
    shutil.rmtree("wifi_setup")
os.mkdir("wifi_setup")
minify(["-c", "-v", "build", "wifi_setup"])

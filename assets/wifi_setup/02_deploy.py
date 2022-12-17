import os
import sys

sys.path.insert(0, os.environ["MP_HOME"])
from mp_tools import *

MYDIR = os.path.split(os.path.abspath(__file__))[0]
FRONTEND_DIR = os.path.join(MYDIR, "frontend")

sync(["makedirs", "/www/wifi_setup"])
sync([
    "--quick", "--overwrite", "--contents", "upload",
    os.path.join(FRONTEND_DIR, "wifi_setup"),
    "/www/wifi_setup"
])
sync(["--quick", "--overwrite", "--contents", "upload", MP_LIBS, "/"])

import os
import sys
sys.path.insert(0, os.environ["MP_HOME"])
from mp_tools import *

MYDIR = os.path.split(os.path.abspath(__file__))[0]
TEST_BACKEND_DIR = os.path.join(MYDIR, "test_backend")

sync("--quick --overwrite --contents upload %s /" % TEST_BACKEND_DIR)

import os
import sys

# make `import inventory` / `import scanner` work when pytest is run from anywhere
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

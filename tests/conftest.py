import os
import sys

# Make the plugin's scripts importable as top-level modules in tests.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

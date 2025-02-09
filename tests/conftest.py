import os
import sys

# Ensure that the repository root is in the PYTHONPATH for test discovery
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

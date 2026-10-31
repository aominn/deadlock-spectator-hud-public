"""Command-line entry for the shared local asset preparation engine."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
from asset_prepare import *
if __name__=='__main__':main()

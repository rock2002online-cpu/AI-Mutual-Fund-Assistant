import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from views.sip_calculator_view import render_sip_calculator

render_sip_calculator()
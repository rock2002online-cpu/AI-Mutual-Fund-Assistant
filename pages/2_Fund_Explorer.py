import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from views.fund_explorer_view import render_fund_explorer

render_fund_explorer()
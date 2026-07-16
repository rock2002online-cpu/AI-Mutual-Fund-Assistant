import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from views.ai_advisor_view import render_ai_advisor

render_ai_advisor()
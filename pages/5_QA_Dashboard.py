import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from views.qa_dashboard_view import render_qa_dashboard

render_qa_dashboard()
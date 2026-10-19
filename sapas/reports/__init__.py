# -*- coding: utf-8 -*-
"""
Sapas Test Report Generators Package.
"""

from sapas.reports.html_reporter import generate_html_report
from sapas.reports.summary_reporter import generate_summary_dashboard

__all__ = ["generate_html_report", "generate_summary_dashboard"]

"""Reproducible experiment records and metrics for the Re:Found paper.

This package is deliberately independent from the operational SQLite store.
Research records must survive application resets and must not change camera or
API behaviour merely because measurement is enabled.
"""


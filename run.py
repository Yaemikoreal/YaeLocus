#!/usr/bin/env python
"""
直接运行入口

Usage:
    python run.py
    python run.py -i data/地址.xlsx -c "详细地址"
"""

from geocode.main import main

if __name__ == "__main__":
    main()
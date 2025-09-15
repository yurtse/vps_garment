#!/usr/bin/env python
"""Modified manage.py to load config.settings.development by default"""
import os
import sys

# ensure code directory (./app) is on sys.path when running from repo root
CODE_DIR = os.path.join(os.path.dirname(__file__), "app")
if os.path.isdir(CODE_DIR) and CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise
    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()

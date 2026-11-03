"""
Entry point for the GUI frontend.

This is the intended target for packaging with PyInstaller, e.g.:
    pyinstaller --onefile --windowed --add-data "assets;assets" run_gui.py
"""

from gui.app import main

if __name__ == "__main__":
    main()

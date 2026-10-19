import argparse
import sys
from PySide6.QtWidgets import QApplication
from .ui import Window


def main():
    parser = argparse.ArgumentParser(description='Student directional gaze keyboard prototype')
    parser.add_argument('--simulate', action='store_true', help='No camera; simulate gaze and closure from visible debug controls')
    args = parser.parse_args()
    application = QApplication(sys.argv[:1])
    window = Window(args.simulate)
    window.show()
    return application.exec()


if __name__ == '__main__':
    sys.exit(main())

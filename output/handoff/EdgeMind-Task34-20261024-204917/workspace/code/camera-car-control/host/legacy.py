"""Reuse the repository's calibrated motion controller without modifying it."""
import sys
from pathlib import Path

MOTION_HOST = Path(__file__).resolve().parents[2] / 'fpga' / 'acg720-motion-control' / 'host'
if not (MOTION_HOST / 'car_control.py').is_file():
    raise RuntimeError(f'Motion controller sources are missing: {MOTION_HOST}')
sys.path.insert(0, str(MOTION_HOST))

from car_control import CarController, Move  # noqa: E402,F401
from protocol import (ARM, CLEAR_FAULT, GET_CAPABILITIES, GET_STATUS,  # noqa: E402,F401
                      HEARTBEAT, SET_PARAM, SET_WHEEL_SPEED, STOP, DISARM,
                      FrameParser, Status, frame)

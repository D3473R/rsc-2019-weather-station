#!/usr/bin/env python

from __future__ import print_function

import os
import sys
import json
import curses
import random
import locale
import threading
import itertools
import collections
import RPi.GPIO as GPIO
import paho.mqtt.publish as publish

from time import sleep
from asciichartpy import plot
from gpiozero import MCP3008
from datetime import datetime

__author__ = "Fabian Wurster"
__license__ = "MIT"
__version__ = "1.0"
__email__ = "fwurster@stud.hs-heilbronn.de"


MQTT_SERVER = 'localhost'
MQTT_PATH = 'weather'

SPEED_PIN = 25
DIRECTION_ERROR = 359
DIRECTION_PRECISION = 0.015
SEND_SLEEP = 0.2

SPEED_KMH = 2.5
SPEED_MS = SPEED_KMH / 3.6

DIRECTIONS = {3.84: 0, 1.98: 22.5, 2.25: 45, 0.41: 67.5, 0.45: 90, 0.32: 112.5, 0.9: 135, 0.62: 157.5, 1.4: 180, 1.19: 202.5, 3.08: 225, 2.93: 247.5, 4.62: 270, 4.04: 292.5, 4.33: 315, 3.43: 337.5}

GPIO.setmode(GPIO.BCM)
GPIO.setup(SPEED_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

ENABLE_GUI = True

locale.setlocale(locale.LC_ALL, 'C.UTF-8')

rows, columns = os.popen('stty size', 'r').read().split()
rows = int(rows)
columns = int(columns)

plot_width = int(columns * 0.8)
tmp = MCP3008(channel=0, device=0)

speed = 0.0
speed_counter = 0
speed_lock = threading.Lock()

def speed_switch(channel):
    global speed_counter

    with speed_lock:
        speed_counter += 1

def speed_timer():
    global speed
    global speed_counter

    while True:
        with speed_lock:
            speed = round(SPEED_MS * speed_counter, 2)
            speed_counter = 0
        sleep(1)

GPIO.add_event_detect(SPEED_PIN, GPIO.RISING, callback=speed_switch)

def gui(scr):

    scr.clear()
    deque_dir = collections.deque([0] * plot_width, maxlen=plot_width)
    deque_speed = collections.deque([0] * plot_width, maxlen=plot_width)

    while(True):
        value = tmp.value * 5.0
        direction = map_direction(value)
        deque_dir.popleft()
        deque_speed.popleft()
        deque_dir.append(direction)
        deque_speed.append(speed)
        scr.addstr(0,0, 'DIRECTION')
        scr.addstr(2, 0, plot(deque_dir, {'minimum': 0.0, 'maximum': 360.0, 'height': 16 }))
        scr.addstr(20, 0, 'SPEED')
        scr.addstr(22, 0, plot(deque_speed, {'minimum': 0.0, 'maximum': 20, 'height': 20 }))
        scr.refresh()
        publish.single(MQTT_PATH, build_json_package(direction, speed), hostname=MQTT_SERVER)
        sleep(SEND_SLEEP)

def headless():
    while(True):
        value = tmp.value * 5.0
        direction = map_direction(value)
        publish.single(MQTT_PATH, build_json_package(direction, speed), hostname=MQTT_SERVER)
        sleep(SEND_SLEEP)

def map_direction(direction_voltage):
    for voltage in DIRECTIONS:
        if abs(voltage - direction_voltage) < DIRECTION_PRECISION:
            return DIRECTIONS.get(voltage)
    return DIRECTION_ERROR

def build_json_package(direction, speed):
    return json.dumps({'speed': speed, 'direction': direction, 'timestamp': datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')})

if __name__ == '__main__':
    try:
        t1 = threading.Thread(target=speed_timer)
        t1.start()
        if ENABLE_GUI:
            curses.wrapper(gui)
        else:
            headless()
    except KeyboardInterrupt:
        try:
            GPIO.cleanup()
            sys.exit(0)
        except SystemExit:
            os._exit(0)

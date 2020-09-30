#!/usr/bin/python3

import sys,os

import npyscreen
import json

import paho.mqtt.client as paho

class MyTheme(npyscreen.ThemeManager):
    default_colors = {
        'DEFAULT'     : 'BLACK_WHITE',
        'FORMDEFAULT' : 'BLACK_WHITE',
        'NO_EDIT'     : 'BLUE_BLACK',
        'STANDOUT'    : 'CYAN_BLACK',
        'CURSOR'      : 'WHITE_BLACK',
        'CURSOR_INVERSE': 'BLACK_WHITE',
        'LABEL'       : 'GREEN_BLACK',
        'LABELBOLD'   : 'WHITE_BLACK',
        'CONTROL'     : 'YELLOW_BLACK',
        'WARNING'     : 'RED_BLACK',
        'CRITICAL'    : 'BLACK_RED',
        'GOOD'        : 'GREEN_BLACK',
        'GOODHL'      : 'GREEN_BLACK',
        'VERYGOOD'    : 'BLACK_GREEN',
        'CAUTION'     : 'YELLOW_BLACK',
        'CAUTIONHL'   : 'BLACK_YELLOW',
    }

class ColorBox(npyscreen.wgwidget.Widget):
    """
    Draws a box on the screen, filled with the specified background
    color.
    """
    def __init__(self, screen, footer=None, *args, **keywords):
        super(ColorBox, self).__init__(screen, editable=False, *args, **keywords)
        self.footer = footer
        if 'color' in keywords:
            self.color = keywords['color'] or 'LABEL'
        else:
            self.color = 'LABEL'

    def update(self, clear=True):
        if clear: self.clear()
        if self.hidden:
            self.clear()
            return False

        HEIGHT = self.height - 1
        WIDTH = self.width - 1

        # draw box.
        for y in range(self.rely, self.rely + HEIGHT):
            self.parent.curses_pad.hline(y, self.relx, ' ', WIDTH, self.parent.theme_manager.findPair(self, self.color))

    def when_value_edited(self):
        self.editing = False

class UX(npyscreen.FormBaseNew):

    def __init__(self, sensor, *args, **kwargs):
        npyscreen.setTheme(MyTheme)

        super().__init__(lines=20, columns=40, *args, **kwargs)
        self.keypress_timeout = 1
        self._sensor = sensor

        self.name = "Occupancy Sensor (%s %s)"%(self._sensor.floor, self._sensor.room)

    def create(self):
        self._box = self.add(ColorBox, width=20, height=10, relx=9, rely=3)
        self._msg1 = self.add(npyscreen.wgtextbox.TextfieldBase, relx=17, rely=7, editable=False)
        self._msg2 = self.add(npyscreen.wgtextbox.TextfieldBase, relx=16, rely=11, editable=False)
        self._enter = self.add(npyscreen.ButtonPress, name = "Enter", width=10, relx=5, rely=-4, color='CURSOR_INVERSE', when_pressed_function=self.enter_press)
        self._leave = self.add(npyscreen.ButtonPress, name = "Leave", relx=25, rely=-4, color='CURSOR_INVERSE', when_pressed_function=self.leave_press)

    def while_waiting(self):
        self.update()

    def update(self):
        self._msg2.value = "(%s/%s)"%(self._sensor.occupancy_cur, self._sensor.occupancy_max)
        if self._sensor.is_full():
            self._box.color = 'CRITICAL'
            self._msg1.color = 'CRITICAL'
            self._msg2.color = 'CRITICAL'
            self._msg1.value = "WAIT"
        else:
            self._box.color = 'VERYGOOD'
            self._msg1.color = 'VERYGOOD'
            self._msg2.color = 'VERYGOOD'
            self._msg1.value = "GO"
        self.display()

    def enter_press(self):
        self._sensor.on_enter()

    def leave_press(self):
        self._sensor.on_leave()

class Protocol(object):

    def __init__(self, sensor, broker, floor, room):
        self._sensor = sensor
        self._broker = broker

        self._name = "%s/%s"%(floor, room)
        self._topic = "sensors/%s/occupancy"%(self._name)

        self._client = paho.Client(self._name, False)
        self._client.on_connect = self.on_connect
        self._client.on_message = self.on_message

        self.start()

    def start(self):
        self._client.connect_async(self._broker)
        self._client.loop_start()

    def on_connect(self, client, userdata, flags, rc):
        self._client.subscribe(self._topic + "/max")

    def on_message(self, client, userdata, msg):
        payload = json.loads(msg.payload)
        if payload['value']:
            self._sensor.occupancy_max = payload['value']
        else:
            self._sensor.occupancy_max = 0

    def publish_change(self):
        payload = {"value" : self._sensor.occupancy_cur}
        try:
            self._client.publish(self._topic + "/cur", json.dumps(payload), qos=2, retain=True)
        except Exception as e:
            print(e)
            raise(e)

class OccupancySensor(npyscreen.NPSAppManaged):

    def __init__(self, broker, floor, room):
        super().__init__()
        self.broker = broker
        self.floor = floor
        self.room = room

        self.occupancy_max = 2
        self.occupancy_cur = 0

    def onStart(self):
        self.ux = self.addForm("MAIN", UX, self)
        self.protocol = Protocol(self, self.broker,
                                 self.floor, self.room)

        self.protocol.publish_change()

    def is_full(self):
        return self.occupancy_cur >= self.occupancy_max

    def on_enter(self):
        self.occupancy_cur += 1
        self.protocol.publish_change()

    def on_leave(self):
        if self.occupancy_cur > 0:
            self.occupancy_cur -= 1
        self.protocol.publish_change()

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ACME Room Occupancy Sensor")
    parser.add_argument("-b", "--broker", help="MQTT broker address", required=True)
    parser.add_argument("-f", "--floor", help="Floor where sensor is located", required=True)
    parser.add_argument("-r", "--room", help="Room where sensor is located", required=True)

    args = parser.parse_args()

    App = OccupancySensor(args.broker, args.floor, args.room)
    try:
        App.run()
    except KeyboardInterrupt:
        pass

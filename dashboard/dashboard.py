import json
import re

from collections import namedtuple

import dash_devices
from dash_devices.dependencies import Input, Output, State

import dash_daq as daq
import dash_bootstrap_components as dbc
import dash_html_components as html

import paho.mqtt.client as paho

import pickledb

class RoomView(dbc.Card):

    @staticmethod
    def make(monitor, room):
        view = RoomView(monitor, room)

        @monitor.view.callback(
            Output(view.tank.id, 'max'),
            [Input(view.input.id, 'value')])
        def update_max(value):
            try:
                room.occupancy_max = value
                return room.occupancy_max
            except Exception as e:
                print(e)
                raise(e)

        monitor.view.clientside_callback(
            """
            function(value, max) {
                if (value < max) {
                    return 'lightgreen';
                } else if (value == max) {
                    return 'lemonchiffon';
                } else {
                    return 'lightcoral';
                }
            }
            """,
            Output(view.tank.id, 'color'),
            [Input(view.tank.id, 'value'),
             Input(view.tank.id, 'max')]
        )

        monitor.view.clientside_callback(
            """
            function(value, max) {
                return value + "/" + max + " people"
            }
            """,
            Output(view.label.id, 'children'),
            [Input(view.tank.id, 'value'),
             Input(view.tank.id, 'max')]
        )

        return view

    TANK_STYLE = {'marginLeft': '1em',
                  'marginTop' : '1.5em',
                  'marginBottom' : '1.5em'}

    def __init__(self, monitor, room):
        super().__init__(className=['text-center', 'm-2'])

        self.monitor = monitor
        self.room= room

        self.title = html.H5(room.name, className='card-title')
        self.tank  = daq.Tank(id='tank-%s'%(room.id,),
                              style=RoomView.TANK_STYLE, scale={'interval': 1},
                              min=0, value=room.occupancy_cur, max=self.room.occupancy_max)
        self.label = html.P(id='label-%s'%(room.id,),
                            children="0/0 people")
        self.input = daq.NumericInput(id='input-%s'%(room.id,),
                                      min=1, value=room.occupancy_max,
                                      label='Max', labelPosition='top')

        self.update_color()
        self.update_label()

        self.children = [dbc.CardBody([self.title, self.tank, self.label, self.input])]

    def update_color(self):
        if self.room.occupancy_cur < self.room.occupancy_max:
            self.tank.color = 'lightgreen'
        elif self.room.occupancy_cur == self.room.occupancy_max:
            self.tank.color = 'lemonchiffon'
        else:
            self.tank.color = 'lightcoral'

    def update_label(self):
        self.label.children = "%s/%s people"%(self.room.occupancy_cur,
                                              self.room.occupancy_max)

class Room(object):

    class Id(namedtuple('Id', ('floor', 'room'))):
        def __str__(self):
            return '%s-%s'%(self.floor, self.room)

        @staticmethod
        def from_str(id):
            return Room.Id(*id.split('-'))

    def __init__(self, monitor, id):
        self._monitor = monitor
        self._id = id
        self._occupancy_max = monitor.db.get(str(id)) or 1
        self._occupancy_cur = 0

        self._view = RoomView.make(monitor, self)

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return '%s %s'%(self.id.floor, self.id.room)

    @property
    def view(self):
        return self._view

    @property
    def occupancy_max(self):
        return self._occupancy_max

    @occupancy_max.setter
    def occupancy_max(self, value):
        if not value or value == self._occupancy_max:
            return

        self._occupancy_max = value
        self._monitor.db.set(str(self.id), value)
        self._monitor.db.dump()

        self.view.input.value = value
        self.view.tank.max = value
        self.view.update_color()

        self._monitor.view.push_mods({
            self.view.input.id : {'value' : value},
            self.view.tank.id : {'max' : value}
        })

        self._monitor.proto.publish_max(self.id, value)

    @property
    def occupancy_cur(self):
        return self._occupancy_cur

    @occupancy_cur.setter
    def occupancy_cur(self, value):
        self._occupancy_cur = value

        self.view.tank.value = value
        self.view.update_color()

        self._monitor.view.push_mods({
            self.view.tank.id : {'value' : value}
        })

class Protocol(object):

    @staticmethod
    def roomid_from_topic(topic):
        pattern = r"sensors/(\w+)/(\w+)/occupancy/cur"
        floor, room = re.match(pattern, topic).groups()
        return Room.Id(floor, room)

    def __init__(self, broker, monitor):
        self._broker = broker
        self._monitor = monitor

        self._name = "backend"

        self._client = paho.Client(self._name, False)
        self._client.on_connect = self.on_connect
        self._client.on_message = self.on_message

        self.start()

    def start(self):
        self._client.connect_async(self._broker)
        self._client.loop_start()

    def on_connect(self, client, userdata, flags, rc):
        topic = self._topic = "sensors/+/+/occupancy/cur"
        self._client.subscribe(topic)

    def on_message(self, client, userdata, msg):
        try:
            room = self._monitor.ensure_room(Protocol.roomid_from_topic(msg.topic))
            room.occupancy_cur = json.loads(msg.payload)['value']
        except Exception as e:
            print(e)
            raise(e)

    def publish_max(self, id, max):
        topic = "sensors/%s/%s/occupancy/max"%(id.floor, id.room)
        payload = {"value" : max}
        self._client.publish(topic, json.dumps(payload), qos=1, retain=True)


class Monitor(object):

    def __init__(self, broker):
        super().__init__()
        self._rooms = {}

        self.view = dash_devices.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
        self.view.config.suppress_callback_exceptions = True
        self.view.layout = self.layout

        self.db = pickledb.load('rooms.db', 1)
        self.proto = Protocol(broker, self)

    def layout(self):
        return dbc.Container([
            html.H1(children='ACME Room Occupancy Monitor'),
            html.Hr(),
            dbc.Row([r.view for r in self.rooms()],
                    id="rooms",
                    className=['row-cols-1', 'row-cols-sm-2', 'row-cols-md-3', 'row-cols-lg-4', 'row-cols-xl-6'])
        ], fluid=False)

    def get_room(self, roomid):
        return self._rooms[roomid]

    def create_room(self, roomid):
        room = Room(self, roomid)
        self._rooms[room.id] = room
        return room

    def ensure_room(self, roomid):
        if not roomid in self._rooms:
            room = self.create_room(roomid)
        return self.get_room(roomid)

    def rooms(self):
        return list(self._rooms.values())

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description="ACME Room Occupancy Monitor")
    parser.add_argument("-b", "--broker", help="MQTT broker address", required=True)
    parser.add_argument("-l", "--listen", help="Dashboard listen address", default="::")
    parser.add_argument("-p", "--port", help="Dashboard listen port", default=8050)

    args = parser.parse_args()

    monitor = Monitor(args.broker)
    monitor.view.run_server(host=args.listen, port=args.port, debug=True)

import logging
import ssl
import websockets
import asyncio
import sys
import re
from asyncio import CancelledError
from collections import deque

import hbmqtt

from functools import partial
from transitions import Machine, MachineError
from hbmqtt.broker import *
from hbmqtt.session import Session
from hbmqtt.mqtt.protocol.broker_handler import BrokerProtocolHandler
from hbmqtt.errors import HBMQTTException, MQTTException
from hbmqtt.utils import format_client_message, gen_client_id
from hbmqtt.adapters import (
    StreamReaderAdapter,
    StreamWriterAdapter,
    ReaderAdapter,
    WriterAdapter,
    WebSocketsReader,
    WebSocketsWriter)
from hbmqtt.plugins.manager import PluginManager, BaseContext


# Monkeypatch the "start" method to correctly parse IPv6 addresses and ports
@asyncio.coroutine
def broker_start_ipv6(self):
    """
        Start the broker to serve with the given configuration
        Start method opens network sockets and will start listening for incoming connections.
        This method is a *coroutine*.
    """
    try:
        self._sessions = dict()
        self._subscriptions = dict()
        self._retained_messages = dict()
        self.transitions.start()
        self.logger.debug("Broker starting")
    except (MachineError, ValueError) as exc:
        # Backwards compat: MachineError is raised by transitions < 0.5.0.
        self.logger.warning("[WARN-0001] Invalid method call at this moment: %s" % exc)
        raise BrokerException("Broker instance can't be started: %s" % exc)

    yield from self.plugins_manager.fire_event(EVENT_BROKER_PRE_START)
    try:
        # Start network listeners
        for listener_name in self.listeners_config:
            listener = self.listeners_config[listener_name]

            if 'bind' not in listener:
                self.logger.debug("Listener configuration '%s' is not bound" % listener_name)
            else:
                # Max connections
                try:
                    max_connections = listener['max_connections']
                except KeyError:
                    max_connections = -1

                # SSL Context
                sc = None

                # accept string "on" / "off" or boolean
                ssl_active = listener.get('ssl', False)
                if isinstance(ssl_active, str):
                    ssl_active = ssl_active.upper() == 'ON'

                if ssl_active:
                    try:
                        sc = ssl.create_default_context(
                            ssl.Purpose.CLIENT_AUTH,
                            cafile=listener.get('cafile'),
                            capath=listener.get('capath'),
                            cadata=listener.get('cadata')
                        )
                        sc.load_cert_chain(listener['certfile'], listener['keyfile'])
                        sc.verify_mode = ssl.CERT_OPTIONAL
                    except KeyError as ke:
                        raise BrokerException("'certfile' or 'keyfile' configuration parameter missing: %s" % ke)
                    except FileNotFoundError as fnfe:
                        raise BrokerException("Can't read cert files '%s' or '%s' : %s" %
                                              (listener['certfile'], listener['keyfile'], fnfe))

                address, s_port = listener['bind'].rsplit(':', 1)
                port = 0
                try:
                    port = int(s_port)
                except ValueError as ve:
                    raise BrokerException("Invalid port value in bind value: %s" % listener['bind'])

                if listener['type'] == 'tcp':
                    cb_partial = partial(self.stream_connected, listener_name=listener_name)
                    instance = yield from asyncio.start_server(cb_partial,
                                                               address,
                                                               port,
                                                               reuse_address=True,
                                                               ssl=sc,
                                                               loop=self._loop)
                    self._servers[listener_name] = Server(listener_name, instance, max_connections, self._loop)
                elif listener['type'] == 'ws':
                    cb_partial = partial(self.ws_connected, listener_name=listener_name)
                    instance = yield from websockets.serve(cb_partial, address, port, ssl=sc, loop=self._loop,
                                                           subprotocols=['mqtt'])
                    self._servers[listener_name] = Server(listener_name, instance, max_connections, self._loop)

                self.logger.info("Listener '%s' bind to %s (max_connections=%d)" %
                                 (listener_name, listener['bind'], max_connections))

        self.transitions.starting_success()
        yield from self.plugins_manager.fire_event(EVENT_BROKER_POST_START)

        #Start broadcast loop
        self._broadcast_task = asyncio.ensure_future(self._broadcast_loop(), loop=self._loop)

        self.logger.debug("Broker started")
    except Exception as e:
        self.logger.error("Broker startup failed: %s" % e)
        self.transitions.starting_fail()
        raise BrokerException("Broker instance can't be started: %s" % e)

hbmqtt.broker.Broker.start = broker_start_ipv6

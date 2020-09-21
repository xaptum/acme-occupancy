import logging
import asyncio
import os
from hbmqtt.broker import Broker

import monkeypatch

logger = logging.getLogger(__name__)

config = {
    'listeners': {
        'default': {
            'type': 'tcp',
            'bind': ':::1883',
        },
    },
    'sys_interval': 10,
    'topic-check': {
        'enabled': False,
        'acl' : {
#            "anonymous": ["sensors/1900/541/occupancy", "sensors/+/+/occupancy"]
            'anonymous': ["#"]
        }
    }
}

broker = Broker(config)

@asyncio.coroutine
def test_coro():
    yield from broker.start()
    #yield from asyncio.sleep(5)
    #yield from broker.shutdown()


if __name__ == '__main__':
    formatter = "[%(asctime)s] :: %(levelname)s :: %(name)s :: %(message)s"
    logging.basicConfig(level=logging.INFO, format=formatter)
    asyncio.get_event_loop().run_until_complete(test_coro())
    asyncio.get_event_loop().run_forever()

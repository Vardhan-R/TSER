from pubnub.callbacks import SubscribeCallback
from pubnub.enums import PNStatusCategory
from pubnub.pnconfiguration import PNConfiguration
from pubnub.pubnub import PubNub
import os
import sys
import time

user_id = sys.argv[1]
pnconfig = PNConfiguration()
pnconfig.publish_key = 'demo'
pnconfig.subscribe_key = 'demo'
pnconfig.user_id = user_id
pnconfig.ssl = True
pubnub = PubNub(pnconfig)

def my_publish_callback(envelope, status):
    # Check whether request successfully completed or not
    if not status.is_error():
        pass

class MySubscribeCallback(SubscribeCallback):
    def presence(self, pubnub, presence):
        pass

    def status(self, pubnub, status):
        pass

    def message(self, pubnub, message):
        if message.publisher == user_id:
            return

        print("From device " + message.publisher + ": " + message.message)

pubnub.add_listener(MySubscribeCallback())
pubnub.subscribe().channels("chan-1").execute()

# Publish a message
try:
    i = 0
    while True:
        time.sleep(1)
        msg = f"This is a test message ({i})."
        pubnub.publish().channel("chan-1").message(msg).pn_async(my_publish_callback)
        i += 1
except KeyboardInterrupt:
    os._exit(1)

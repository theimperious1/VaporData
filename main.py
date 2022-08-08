#!/usr/bin/env python
import logging

from Server import VaporServe
from DataManager import DataManager
from threading import Thread

# Set up logging
formatting = "[%(asctime)s] [%(levelname)s:%(name)s] %(message)s"
# noinspection PyArgumentList
logging.basicConfig(
    format=formatting,
    level=logging.INFO,
    handlers=[logging.FileHandler('vapor.log', encoding='utf8'),
              logging.StreamHandler()])
logger = logging.getLogger(__name__)


def start():
    # TODO: Find a better way to do this. Improper use of globals I think?
    global data_manager
    data_manager = DataManager()
    global stop_thread
    stop_thread = False

    update_thread = Thread(target=update)
    update_thread.start()

    server = VaporServe(data_manager)
    server.start()


def update():
    while not stop_thread:
        # TODO: Fix fetches. They are returning nothing. IP potentially blocked?
        # data_manager.fetch_transactions()
        # data_manager.fetch_wallets()
        data_manager.update_nodes()


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    start()

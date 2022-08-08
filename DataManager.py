import json
import sqlite3
import time
import traceback
from threading import Lock
import requests
import logging
from abi import abi
from web3 import Web3

API_URL = 'https://io.dexscreener.com/u/trading-history/recent/avalanche/0x4cd20F3e2894Ed1A0F4668d953a98E689c647bfE'

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; rv:91.0) Gecko/20100101 Firefox/91.0',
    'Origin': 'https://dexscreener.com',
    'DNT': '1',
    'Alt-Used': 'io.dexscreener.com',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Connection': 'close'
}

logger = logging.getLogger(__name__)


def format_number(num):
    return float(num.replace(',', ''))


w3 = Web3(Web3.HTTPProvider("https://api.avax.network/ext/bc/C/rpc"))

controllerAddress = "0xD7Ce2935008Ae8ca17E90fbe2410D2DB7608058C"
storageAddress = "0xCd5E168dA3456cD2d5A8ab400f9cebdDC453720d"

# noinspection PyTypeChecker
controllerContract = w3.eth.contract(address=controllerAddress, abi=abi)
# noinspection PyTypeChecker
storageContract = w3.eth.contract(address=storageAddress, abi=abi)

lock = Lock()


# https://io.dexscreener.com/u/trading-history/recent/avalanche/0x4cd20F3e2894Ed1A0F4668d953a98E689c647bfE?t=1655251832001
# anything after the timestamp above will be returned. if param is tb (time before), anything before that will be returned.
# noinspection PyBroadException
class DataManager:

    def __init__(self):
        self.db = sqlite3.connect('data.db', check_same_thread=False)
        self.timestamp = str(int(time.time())) + '000'
        self.transactions = []
        self.wallets = []
        self.vpnd_price = 0
        self.reload_data()

    def fetch_transactions_once(self):
        req = requests.get(f'{API_URL}?tb={self.timestamp}', headers=headers)
        if req.text is None:
            return None
        return json.loads(req.text)

    def fetch_transactions(self):
        iterator = 1
        count = 0
        while 1:
            try:
                data = self.fetch_transactions_once()
                if not data or not self.integrate_data(data):
                    return False

                if iterator % 100:
                    logger.info(f'Loop {count} complete!')
                    iterator = 0
                iterator += 1
                count += 1
            except SystemExit:
                break
            except:
                traceback.print_exc()
                exit()

        return True

    def integrate_data(self, trading_data):
        trades = trading_data['tradingHistory']
        end = len(trades)
        iterator = 0
        for trade in trades:
            if not self.insert(trade):
                return False
            iterator += 1
            if iterator == end:
                self.timestamp = trade['blockTimestamp']

        return True

    def insert(self, transaction):
        if transaction['txnHash'] in self.transactions:
            return False

        transaction = (transaction['blockNumber'], transaction['blockTimestamp'], transaction['txnHash'],
                       transaction['logIndex'], transaction['type'], format_number(transaction['priceUsd']),
                       format_number(transaction['volumeUsd']), format_number(transaction['amount0']),
                       format_number(transaction['amount1']), 0)

        with self.db:
            cur = self.db.cursor()
            cur.execute('INSERT INTO transactions VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT DO NOTHING',
                        transaction)
            self.transactions.append(transaction[2])
            self.db.commit()

        return True

    def reload_data(self):
        with self.db:
            cur = self.db.cursor()
            cur.execute('SELECT txnHash FROM transactions WHERE scraped = 0')
            for row in cur.fetchall():
                self.transactions.append(row[0])
            cur.execute('SELECT * FROM wallets WHERE total_amount != -1 ORDER BY total_amount DESC')
            for row in cur.fetchall():
                self.wallets.append(row)

        try:
            req = requests.get('https://api.coingecko.com/api/v3/simple/price?ids=vapornodes&vs_currencies=usd')
            self.vpnd_price = json.loads(req.text)['vapornodes']['usd']
        except:
            traceback.print_exc()
            self.vpnd_price = 1
        logger.info('Successfully reloaded data!')

    def update_nodes(self, addresses=None):
        i = 0
        # TODO: This var should be in global scope. It is a flag to choose the start index in the event of an abrupt exit/stop.
        start_index = 0
        with self.db:
            cur = self.db.cursor()
            if addresses is None:
                for wallet in self.wallets:
                    addr = wallet[0]
                    if start_index > 0:
                        start_index -= 1
                        i += 1
                        continue

                    self.update_node(addr, cur)
            else:
                for addr in addresses:
                    self.update_node(addr, cur)

                i += 1
                # logger.info(f'{i} - {addr}')

        logger.info('Node update is complete!')
        # print(w3.eth.getTransaction('0x7a9226558e974251ad4814a851ac0c59a6ba903fe973fe6cffb7e71130bc59f2'))

    def update_node(self, addr, cur):
        """
        :param addr: wallet address
        :param cur: sqlite3 database cursor
        :return:
        """
        wallet_address = w3.toChecksumAddress(addr)
        nodes = storageContract.functions.getAllNodes(wallet_address).call()

        node_names, node_amounts = [], []
        total_amount, creation_time, last_claim_time, last_compound_time = -1, -1, -1, -1
        for node in nodes:
            name, creation_time, last_claim_time, last_compound_time, amount, deleted = node
            if deleted:
                continue
            node_names.append(name)
            node_amounts.append(amount / 1e18)
            total_amount += (amount / 1e18)

        cur.execute(
            'UPDATE wallets SET nodes = ?, node_amounts = ?, total_amount = ?, creation_time = ?, last_claim_time = ?, last_compound_time = ? WHERE address = ?',
            (json.dumps(node_names), json.dumps(node_amounts), total_amount, creation_time, last_claim_time,
             last_compound_time, addr))
        self.db.commit()

    def fetch_wallets(self):
        with self.db:
            cur = self.db.cursor()
            i = 1
            # TODO: Do we really need to reverse the transaction array anymore?
            self.transactions.reverse()
            for tx in self.transactions:
                transaction = w3.eth.getTransaction(tx)
                cur.execute(
                    f'INSERT INTO wallets VALUES("{transaction["from"]}", null, null, -1, -1, -1, -1, {int(time.time())}) ON CONFLICT DO NOTHING')
                cur.execute(f"UPDATE transactions SET scraped = 1 WHERE txnHash = '{tx}'")
                self.db.commit()
                # logger.info(f'{i}: {transaction["from"]}')
                i += 1

        logger.info('Wallets have been fetched and updated from latest transaction data!')

    def get_last_timestamp(self):
        return self.timestamp

    def get_db(self):
        return self.db

    def get_transactions(self):
        return self.transactions

    def get_wallets(self):
        return self.wallets

    def get_vpnd_price(self):
        return self.vpnd_price

    def set_vpnd_price(self, price):
        """ temporary function """
        self.vpnd_price = price

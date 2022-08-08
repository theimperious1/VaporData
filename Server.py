import time
import traceback
from io import StringIO
import eventlet
import requests
from eventlet import wsgi
import json
import logging

# Set up logging
logger = logging.getLogger(__name__)


def read_wsgi_input(wsgi_input, length):
    # TODO: Better way of conversion than replacing the b' (and more ' quotes at end) in the string.
    io_data = StringIO(str(wsgi_input.read(length)))
    data = io_data.readlines()
    if len(data) >= 1:
        data = data[0]
    trimmed_data = data.replace("b'", '')
    trimmed_data = trimmed_data[0:len(trimmed_data) - 1]
    return trimmed_data


def validate_number(data):
    if not data.isnumeric():
        return False
    int_num = int(data)
    if int_num <= 6000 and int_num > 0:
        return True

    return False


# TODO: Add compound time to reach next and current rank from last
# TODO: Beautify GUI.
class VaporServe:

    def __init__(self, data_manager):
        eventlet.monkey_patch()
        self.data_manager = data_manager
        self.db = self.data_manager.get_db()

    def start(self):
        logger.info(f'VAPOR SERVER STARTED ON: {time.strftime("%m/%d/%y at %H:%M:%S", time.gmtime(time.time()))}')
        wsgi.server(eventlet.listen(('', 80)), self.dispatch, log_output=False, debug=False)

    def dispatch(self, environ, start_response):
        """Resolves to the web page or the websocket depending on the path."""
        try:
            path = environ['PATH_INFO']

            # content_length = int(environ.get('CONTENT_LENGTH', '0'))
            # data = read_wsgi_input(environ['wsgi.input'], content_length) if content_length > 0 else None

            if '/nodes/top' in path:
                start_response('200 OK', [('content-type', 'text/html')])
                response = self.get_top(start_response, path)
                logger.info('/nodes/top was hit')
            elif path == '/nodes/count':
                start_response('200 OK', [('content-type', 'text/html')])
                response = self.get_count(start_response)
                logger.info('/nodes/count was hit')
            elif '/nodes/search' in path:
                start_response('200 OK', [('content-type', 'text/html')])
                response = self.search(start_response, path)
                logger.info('/nodes/search was hit')
            elif '/nodes/rank' in path:
                start_response('200 OK', [('content-type', 'text/html')])
                response = self.get_rank(start_response, path)
                logger.info('/nodes/rank was hit')
            else:
                start_response('204 No Content', [('content-type', 'text/html')])
                response = ''
                logger.info('An invalid route was hit')

            return '<h1><b>#chickengang</b></h1><br><br>' + response + self.get_alt_urls(
                path[path.rfind('/') + 1: len(path)])
        except:
            logger.info('Error handling dispatch request')
            traceback.print_exc()
            start_response('500 Internal Server Error', [('content-type', 'text/html')])
            return ['']

    def get_top(self, start_response, path):
        i = 1
        filtered_results = []
        count = path[path.rfind('/') + 1: len(path)]
        is_valid_number = validate_number(count)
        if not is_valid_number:
            start_response('400 Bad Request', [('content-type', 'text/html')])
            return json.dumps({
                'type': 'bad_number',
                'status': 'error',
                'reason': f'{count} is either not a number, too high (above 6000), or too low (0 or less)',
            })
        with self.db:
            cur = self.db.cursor()
            cur.execute(
                f'SELECT nodes, node_amounts, total_amount, creation_time FROM wallets ORDER BY total_amount DESC LIMIT {count}')
            results = cur.fetchall()
            for result in results:
                filtered_results.append({
                    'i': i,
                    'nodes': result[0],
                    'node_amounts': result[1],
                    'total_amount': result[2],
                    'creation_time': result[3]
                })
                i += 1

        response = ''
        for result in filtered_results:
            x = f"<b>{result['i']}) Node Names</b> - {result['nodes']}<br><b>Amounts</b>: {result['node_amounts']}<br><b>Total Amount</b>: {result['total_amount']}<br><b>Creation Time</b>: {result['creation_time']}<br><br>"
            response += x
        return response

    def search(self, start_response, path):
        if '0x' not in path:
            start_response('400 Bad Request', [('content-type', 'text/html')])
            return json.dumps({
                'type': 'bad_address',
                'status': 'error',
                'reason': f'The address you provided is not valid. Please ensure the URL looks like this: /nodes/search/0xYourAddress',
            })
        address = path[path.rfind('/') + 1: len(path)]
        with self.db:
            cur = self.db.cursor()
            cur.execute(
                f'SELECT nodes, node_amounts, total_amount, creation_time FROM wallets WHERE LOWER(address) = LOWER(?)', (address,))
            result = cur.fetchone()
            if result is None:
                return 'This address was not found.'

            filtered_result = {
                'nodes': result[0],
                'node_amounts': result[1],
                'total_amount': result[2],
                'creation_time': result[3]
            }
            return '<b>To search an address, replace the 0x address in the address bar at the top of your browser with the desired address. e.g supreme-one.net/nodes/search/PASTE_DESIRED_WALLET_ADDRESS_HERE</b><br><br>' + json.dumps(filtered_result, indent=4)

    def get_rank(self, start_response, path):
        i = 1
        address = path[path.rfind('/') + 1: len(path)]
        with self.data_manager.get_db() as cur:
            self.data_manager.update_node(address, cur)

        last_wallet, next_wallet, target_wallet, response = None, None, None, None

        for wallet in self.data_manager.get_wallets():
            if target_wallet is not None:
                next_wallet = wallet
                break
            if wallet[0].lower() == address.lower():
                response = f'The ranking for {address} is #{i} out of {len(self.data_manager.get_wallets())}!'
                target_wallet = wallet
                if address.lower() == '0x549d7b6feA00FCbC4AA70abeb73Fc1C88D591BD9'.lower():
                    response = 'Hey, this is my creator!<br>' + response
                elif i <= 100 and i > 10:
                    response = "You're a pretty big fish!<br>" + response
                elif i == 1:
                    response = 'Damn, what a big chicken!<br>' + response
                elif i <= 10:
                    response = "You're a whale!\n" + response
            else:
                last_wallet = wallet
            i += 1

        return self.get_level_up_info(i, target_wallet, last_wallet, next_wallet, response) if target_wallet is not None \
            else f"{address} was not found. If your wallet is new, try again in a few hours."

    def get_count(self, start_response):
        """
        :param start_response:
        :return:
        """
        return f'There is currently {len(self.data_manager.get_wallets())} wallets with nodes. ' \
               f'<b>NOTICE</b>: I am missing around 4000 noded wallets at this time.'

    def get_alt_urls(self, address):
        """
        :param address: blockchain address to be used e.g: 0x549d7b6feA00FCbC4AA70abeb73Fc1C88D591BD9
        :return: Hyperlinks to other pages with the requested address
        """
        if address is None or '0x' not in address:
            address = '0x549d7b6feA00FCbC4AA70abeb73Fc1C88D591BD9'
        return '<br><br>' \
               '<a href="/nodes/top/100">Show top nodes</a>' \
               '<br>' \
               '<a href="/nodes/count">Show how many nodes are in the database</a>' \
               '<br>' \
               f'<a href="/nodes/search/{address}">Search an address</a>' \
               '<br>' \
               f'<a href="/nodes/rank/{address}">Show your nodes rank</a>'

    def get_level_up_info(self, i, target_wallet, last_wallet, next_wallet, response):
        """
        :param i: Iterator count
        :param target_wallet: Requested wallet
        :param last_wallet: Previous wallet before target_wallet is found
        :param next_wallet: Next wallet after target_wallet is found
        :param response:
        :return: Previous response combined with HTML for ranking and prices to next and last rank
        """
        # This check only matters when checking the #1 wallet.
        next_rank_distance = float("{:.2f}".format(last_wallet[3] - target_wallet[3])) if last_wallet is not None else 0
        last_rank_distance = float("{:.2f}".format(target_wallet[3] - next_wallet[3]))
        try:
            # We fetch on-demand due to there being very little load, not a problem at this time.
            req = requests.get('https://api.coingecko.com/api/v3/simple/price?ids=vapornodes&vs_currencies=usd')
            vpnd_price = json.loads(req.text)['vapornodes']['usd']
            self.data_manager.set_vpnd_price(vpnd_price)
        except:
            traceback.print_exc()
            vpnd_price = self.data_manager.get_vpnd_price()

        next_price, last_price = float("{:.2f}".format(next_rank_distance * vpnd_price)), float(
            "{:.2f}".format(last_rank_distance * vpnd_price))
        return response + '<br><br>' \
                          f'You are <b>{next_rank_distance}</b> $VPND from rank #{i - 2} and <b>{last_rank_distance}</b> from rank #{i}' \
                          '<br>' \
                          f'It would cost <b>${next_price}</b> to level up to the next rank, and the ' \
                          f'wallet following you would need to spend <b>${last_price}</b> to surpass you.'

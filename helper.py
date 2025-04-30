from time import sleep
import signal
import requests
import storage_model

class ApiException(Exception):
    pass

# Signal handler for graceful shutdown when CTRL+C is pressed
def signal_handler(signum, frame):
    global shutdown
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    shutdown = True

API_KEY = {'X-API-Key': 'M9T7LZRF'}
shutdown = False

# Create a session with the API key set
def create_session():
    s = requests.Session()
    s.headers.update(API_KEY)
    return s

# Get the current 'tick' of the running case
def get_tick(session, round):
    resp = session.get('http://localhost:9999/v1/case')
    if resp.status_code == 401:
        raise ApiException('Response error in get_tick')
    case = resp.json()
    if round == 1:
        return case['tick']
    else:
        return case['tick'] + 600

# Get bid and ask for a given security
def ticker_bid_ask(session, ticker):
    payload = {'ticker': ticker}
    resp = session.get('http://localhost:9999/v1/securities/book', params=payload)
    if resp.ok:
        book = resp.json()
        # Only return if there are any actual bids
        if len(book['bids']) > 0 and len(book['asks']) > 0:
            return book['bids'], book['asks']
    raise ApiException('Response error in ticker_bid_ask')

# Get the position for a specific ticker
def get_position(session, ticker):
    payload = {'ticker': ticker}
    resp = session.get('http://localhost:9999/v1/securities', params=payload)
    if resp.ok:
        position = resp.json()
        return position[0]["position"]
    else:
        print(f"Error fetching position for {ticker}: {resp.status_code}")
        return 0
    
def place_market_order(session, ticker, action, quantity):
    order = {
        'ticker': ticker,
        'type': "MARKET",
        'quantity': quantity,
        'action': action,
    }
    resp = session.post('http://localhost:9999/v1/orders', params=order)
    if resp.ok:
        order_details = resp.json()
        print(f"Market order placed: {action} {quantity} of {ticker}")
        return order_details
    raise Exception(f"Error placing limit order for {ticker}: {resp.text}")


def how_much_CL_I_can_refine(session, hedge, refinery_hedged):
   storage_model.end_unused_storage(session)
   a = int(get_position(session, "CL-2F"))
   b = int(get_position(session, "CL-1F"))
   c = int(get_position(session, "CL"))
   d = int(get_position(session, "CL-AK"))
   e = int(get_position(session, "CL-NYC"))
   net_pos = a + b + c + d + e
   if net_pos > 70:
       position = int((get_position(session, "CL") / 10))
       order_quantity = 3- position
       place_market_order(session, "CL-2F", "SELL", 30)
       if order_quantity > 0:
        for _ in range(order_quantity):
            storage_model.lease_storage(session, "CL-STORAGE")
       place_market_order(session, "CL", "BUY", 30)
   else:
        position = int((get_position(session, "CL") / 10))
        order_quantity = 3- position
        place_market_order(session, "CL-2F", "SELL", 30)
        if order_quantity > 0:
         for _ in range(order_quantity):
            storage_model.lease_storage(session, "CL-STORAGE")
        place_market_order(session, "CL", "BUY", 30)
        place_market_order(session, "CL-2F", "SELL", 30)
   if hedge == False:
         place_market_order(session, "CL-2F", "BUY", 30)
   else:
        return refinery_hedged == True
   
def sell_refinery_positions(session, hedge, refinery_hedged):
    a = int(get_position(session, "CL-2F"))
    b = int(get_position(session, "CL-1F"))
    c = int(get_position(session, "CL"))
    d = int(get_position(session, "CL-AK"))
    e = int(get_position(session, "CL-NYC"))
    net_pos = int(a + b + c + d + e)
    if net_pos > -70:
        place_market_order(session, "CL-2F", "BUY", 30)
        place_market_order(session, "HO", "SELL", 10)
        place_market_order(session, "RB", "SELL", 20)
    else:
        place_market_order(session, "CL", "SELL", 30)
        place_market_order(session, "CL-2F", "BUY", 30)
    if refinery_hedged == False:
        place_market_order(session, "CL-2F", "SELL", 30)
    else:
        refinery_hedged = False

def net_positions(session):
    a = int(get_position(session, "CL-2F"))
    b = int(get_position(session, "CL-1F"))
    c = int(get_position(session, "CL"))
    d = int(get_position(session, "CL-AK"))
    e = int(get_position(session, "CL-NYC"))
    net_pos = a + b + c + d + e
    return net_pos



def fill_up_leases(session):
    resp = session.get('http://localhost:9999/v1/leases')
    for lease in resp.json():
        if not isinstance(lease, str) and lease['containment_usage'] == 0:
            if get_tick(session, round) - lease["start_lease_tick"] <= 1:
                lease_ticker = lease['ticker']
                place_market_order(session, lease_ticker, "BUY", )

def get_net_position(session):
    resp = session.get('http://localhost:9999/v1/limits')
    limits = resp.json()
    return limits[0]['net']

def try_to_order(session, ticker, action, quantity):
    net = get_net_position(session)
    quantity = int(quantity)
    
    max_position = 100
    min_position = -100

    # Calculate how much room is left based on the action
    if action == "BUY":
        max_allowed = max_position - net
    elif action == "SELL":
        max_allowed = net - min_position
    else:
        print(f"Invalid action: {action}")
        return

    # Limit order size to what's allowed
    allowed_quantity = min(quantity, max_allowed)
    
    if allowed_quantity <= 0:
        print(f"Cannot place order: would exceed net position limit. Net = {net}, Action = {action}")
        return

    # Place orders in batches of 10
    for _ in range(int(allowed_quantity // 10)):
        place_market_order(session, ticker, action, 10)


def get_storage_leases(session, storage_name):
    resp = session.get('http://localhost:9999/v1/leases')
    if not resp.ok:
        return 0
    count = 0
    for lease in resp.json():
        if isinstance(lease, dict) and lease['ticker'] == storage_name:
            count += 1
    return count


from time import sleep
import signal
import requests

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
def get_tick(session):
    resp = session.get('http://localhost:9999/v1/case')
    if resp.status_code == 401:
        raise ApiException('Response error in get_tick')
    case = resp.json()
    return case['tick']

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

# Get price history for volatility calculation
def get_price_history(session, ticker, num_ticks=10):
    payload = {'ticker': ticker}
    resp = session.get('http://localhost:9999/v1/securities/history', params=payload)
    if resp.ok:
        history = resp.json()
        
        # Get the most recent 'num_ticks' entries
        recent_history = history[:num_ticks]
        
        # Extract the prices from the 'close' field
        prices = [entry['close'] for entry in recent_history]
        return prices
    return []

# Combine order books and calculate best prices based on tender type
def combined_best_prices(session, ticker):
    bid = []
    ask = []

    if ticker.endswith("_M"):
        # If the ticker ends with "_M", get both the "_M" and "_A" versions
        bid_m, ask_m = ticker_bid_ask(session, ticker)
        bid_a, ask_a = ticker_bid_ask(session, ticker[:-2] + "_A")
        
        bid.extend(bid_m)
        bid.extend(bid_a)
        ask.extend(ask_m)
        ask.extend(ask_a)
    else:
        bid, ask = ticker_bid_ask(session, ticker)

    # Sort bids in descending order and asks in ascending order
    bid.sort(key=lambda x: x['price'], reverse=True)
    ask.sort(key=lambda x: x['price'])

    return bid, ask

# Calculate the average price based on the available quantity in the book
def calculate_average_price(bids, asks, quantity_needed, tender_action):
    total_quantity = 0
    total_price = 0

    # Select the relevant price list based on the tender action
    if tender_action == "SELL":
        orders = asks
    elif tender_action == "BUY":
        orders = bids
    else:
        raise ValueError("Invalid tender action. Must be 'BUY' or 'SELL'.")

    # Sort orders based on action (highest prices for sell, lowest prices for buy)
    if tender_action == "SELL":
        orders.sort(key=lambda x: x['price'])
    else:
        orders.sort(key=lambda x: x['price'], reverse=True)

    # Accumulate quantity and price
    for order in orders:
        available_quantity = order['quantity']
        total_quantity += available_quantity
        total_price += order['price'] * available_quantity
        if total_quantity >= quantity_needed:
            break

    if total_quantity < quantity_needed:
        return None, None  # Not enough quantity in the book

    return total_price / total_quantity, total_quantity

# Adjust the threshold based on volatility over the last 10 seconds
def adjust_threshold(session, ticker, base_threshold=0.1):
    price_history = get_price_history(session, ticker)
    if len(price_history) < 2:
        return base_threshold  # Not enough data for volatility calculation

    price_change = abs(price_history[-2] - price_history[-1])
    if price_change > 0.1:
        return base_threshold * 2  # Double the threshold if volatility is high
    return base_threshold

# Decide tenders based on price thresholds and quantity
def tender_orders(session, threshold=0.1):
    resp = session.get('http://localhost:9999/v1/tenders')
    if resp.ok:
        tender = resp.json()
        if len(tender) > 0:
            tenderid = tender[0]['tender_id']
            best_ticker = tender[0]["ticker"]
            bid, ask = combined_best_prices(session, best_ticker)

            if tender[0]["price"] is not None:
                # Adjust the threshold based on volatility
                threshold = adjust_threshold(session, best_ticker, base_threshold=threshold)

                # Handle BUY tender
                if tender[0]['action'] == "BUY":
                    print('Buy tender received')
                    if get_position(session, tender[0]['ticker']) <= 0:
                        quantity_needed = tender[0]["quantity"] / 3
                        avg_price, total_quantity = calculate_average_price(bid, ask, quantity_needed, tender[0]['action'])

                        if avg_price and total_quantity >= quantity_needed:
                            if tender[0]['price'] < avg_price - threshold:
                                resp = session.post(f'http://localhost:9999/v1/tenders/{tenderid}')
                                print(f'Tender BUY accepted at {tender[0]["price"]} for {best_ticker}')
                        else:
                            print(f"Not enough liquidity to fulfill tender for {best_ticker}")

                # Handle SELL tender
                elif tender[0]['action'] == "SELL":
                    print('Sell tender received')
                    if get_position(session, tender[0]['ticker']) >= 0:
                        quantity_needed = tender[0]["quantity"] / 3
                        avg_price, total_quantity = calculate_average_price(bid, ask, quantity_needed, tender[0]['action'])

                        if avg_price and total_quantity >= quantity_needed:
                            if tender[0]['price'] > avg_price + threshold:
                                resp = session.post(f'http://localhost:9999/v1/tenders/{tenderid}')
                                print(f'Tender SELL accepted at {tender[0]["price"]} for {best_ticker}')

#def ensure_storage
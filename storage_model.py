import helper

def CL_future_arb(session, future, tick, round, threshold=.10):
    resp = session.get('http://localhost:9999/v1/securities')
    if resp.ok:
        if future == "CL-2F":
            expected_difference = 2 if round == 1 else 1
        elif future == "CL-1F":
            expected_difference = 1 if round == 1 else .5
        CL_bid, CL_ask = helper.ticker_bid_ask(session, "CL")
        CL_future_bid, CL_future_ask = helper.ticker_bid_ask(session, "CL-2F")
        cl_price = (CL_bid[0]['price'] + CL_ask[0]['price']) / 2
        cl_future_price = (CL_future_bid[0]['price'] + CL_future_ask[0]['price']) / 2
        price_difference = cl_future_price - cl_price
        expected_difference = expected_difference-(.05*(tick/30))
        # If spread is positive the future is overpriced
        # If spread is negative the future is underpriced
        spread = price_difference - expected_difference
        #print(f"CL-2F price: {future_price}, CL price: {cl_price}, Price difference: {price_difference}"
              #f", spread: {spread}, Expected difference: {expected_difference}")
        if cl_future_price is not None and cl_price is not None:
            print(f"CL_position: {helper.get_position(session, 'CL')}, {future}_position: {helper.get_position(session, f'{future}')}")
            if spread > threshold:
                print("trying to lease storage")
                if helper.get_position(session, "CL") < 100:
                    lease_storage(session, "CL-STORAGE")
                    helper.place_market_order(session, "CL", "BUY", 10)
                    helper.place_market_order(session, f"{future}", "SELL", 10)

            elif spread <= 0 :
                if helper.get_position(session, "CL") != 0:
                    helper.place_market_order(session, "CL", "SELL", 10)
                    helper.place_market_order(session, f"{future}", "BUY", 10)
                    end_lease_storage(session, "CL-STORAGE")
            else: 
                print('No action needed')
    else:
        print(f"Error fetching bid/ask prices for CL and {future}")

def lease_storage(session, ticker):
    order = {
        "ticker": ticker
    }
    resp = session.post("http://localhost:9999/v1/leases", params=order)

    if resp.ok:
        print(f"Successfully leased storage for {ticker}.")
        return resp.json()
    raise Exception(f"Error leasing storage for {ticker}: {resp.text}")

def end_lease_storage(session, ticker):
    resp = session.get('http://localhost:9999/v1/leases')
    lease_info = resp.json()
    lease_id = lease_info[0]['id']
    session.delete('http://localhost:9999/v1/leases/{}'.format(lease_id))
    print(f"Successfully ended lease for {ticker}.")

def end_unused_storage(session):
    """Ends all leases that are not in use."""
    resp = session.get('http://localhost:9999/v1/leases')
    leaseinfo = resp.json()
    for x in leaseinfo:
        if not isinstance(x, str):
            if x['containment_usage'] == 0:
                leaseid = x['id']
                session.delete('http://localhost:9999/v1/leases/{}'.format(leaseid))
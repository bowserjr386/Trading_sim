import helper
from time import sleep

def CL_future_arb(session, future, tick, round, hedge, threshold=0.15):
    if future == "CL-2F":
        other_future = "CL-1F"
        expected_difference = 2 if round == 1 else 1
    elif future == "CL-1F":
        other_future = "CL-2F"
        expected_difference = 1

    CL_bid, CL_ask = helper.ticker_bid_ask(session, "CL")
    CL_future_bid, CL_future_ask = helper.ticker_bid_ask(session, future)

    if not CL_bid or not CL_ask or not CL_future_bid or not CL_future_ask:
        print(f"Error fetching bid/ask prices for CL or {future}")
        return

    cl_price = (CL_bid[0]['price'] + CL_ask[0]['price']) / 2
    cl_future_price = (CL_future_bid[0]['price'] + CL_future_ask[0]['price']) / 2

    # Decay expected difference over time
    expected_difference -= 0.05 * (tick / 30)
    spread = cl_future_price - cl_price - expected_difference
    print(f"{future} storage spread: {spread:.2f}")

    # if hedge:
    #     net_pos = int(helper.net_positions(session))
    #     net_CL = int(helper.get_position(session, "CL"))
    #     net_future = int(helper.get_position(session, future))
    #     net_other_future = int(helper.get_position(session, other_future))
    #     container_count = get_storage_count(session)

    #     if spread > threshold:
    #         print(f"Opportunity detected: spread {spread:.2f} > threshold")
    #         if net_pos < 100 and container_count < 10:
    #             print("Leasing storage and entering arbitrage position")
    #             lease_storage(session, "CL-STORAGE")
    #             helper.place_market_order(session, "CL", "BUY", 10)
    #             helper.place_market_order(session, future, "SELL", 10)

    #     elif spread <= .04 and net_CL > 0 and net_pos > -100:
    #         print("Closing arbitrage position")
    #         if net_other_future == 0:
    #             helper.place_market_order(session, "CL", "SELL", 10)
    #             helper.place_market_order(session, future, "BUY", 10)
    #         else:
    #             helper.place_market_order(session, future, "BUY", 10)
    #     else:
    #         print("No storage arbitrage action needed.")

def lease_storage(session, ticker):
    resp = session.post("http://localhost:9999/v1/leases", params={"ticker": ticker})
    if resp.ok:
        print(f"Successfully leased storage for {ticker}.")
        return resp.json()
    raise Exception(f"Error leasing storage for {ticker}: {resp.text}")

def end_lease_storage(session, ticker):
    resp = session.get('http://localhost:9999/v1/leases')
    for lease in resp.json():
        if lease['ticker'] == ticker:
            lease_id = lease['id']
            session.delete(f'http://localhost:9999/v1/leases/{lease_id}')
            print(f"Successfully ended lease for {ticker}.")

def end_unused_storage(session):
    resp = session.get('http://localhost:9999/v1/leases')
    for lease in resp.json():
        if not isinstance(lease, str) and lease['containment_usage'] == 0:
            lease_id = lease['id']
            session.delete(f'http://localhost:9999/v1/leases/{lease_id}')

def get_storage_count(session):
    resp = session.get('http://localhost:9999/v1/leases')
    count = 0
    for lease in resp.json():
        if not isinstance(lease, str) and lease['ticker'] == "CL-STORAGE":
            count += 1
    return count

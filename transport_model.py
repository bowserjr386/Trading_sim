import helper
import storage_model
from time import sleep

MAX_NET_POSITION = 100

def get_pipeline_cost(session, pipeline):
    resp = session.get('http://localhost:9999/v1/assets')
    asset_info = resp.json()
    for asset in asset_info:
        if asset['ticker'] == pipeline:
            return asset['lease_price']
    return 0

def ensure_position_capacity(session, direction, quantity_lots):
    net_pos = helper.get_net_position(session)
    temporary_cl2f_trades = 0

    if direction == "BUY":
        excess = net_pos + quantity_lots * 10 - MAX_NET_POSITION
        if excess > 0:
            temporary_cl2f_trades = (excess + 9) // 10
            for _ in range(int(temporary_cl2f_trades)):
                helper.place_market_order(session, "CL-2F", "SELL", 10)

    elif direction == "SELL":
        excess = -MAX_NET_POSITION - (net_pos - quantity_lots * 10)
        if excess > 0:
            temporary_cl2f_trades = (excess + 9) // 10
            for _ in range(int(temporary_cl2f_trades)):
                helper.place_market_order(session, "CL-2F", "BUY", 10)

    return temporary_cl2f_trades

def unwind_cl2f_offset(session, direction, count):
    opposite = "BUY" if direction == "SELL" else "SELL"
    for _ in range(int(count)):
        helper.place_market_order(session, "CL-2F", opposite, 10)

def decide_transport_arb(session, pipeline, AK_start, NY_start, transporting_AK, transporting_NYC, hedge, using_refinery, threshold=1000):
    pipeline_cost = get_pipeline_cost(session, pipeline)
    pipeline_ticker = "CL-AK" if pipeline == "AK-CS-PIPE" else "CL-NYC"
    CL_bid, CL_ask = helper.ticker_bid_ask(session, "CL")
    pipeline_bid, pipeline_ask = helper.ticker_bid_ask(session, pipeline_ticker)

    if pipeline_bid is not None and CL_bid is not None:
        net_pos = helper.get_net_position(session)

        # AK → CS
        if pipeline == "AK-CS-PIPE" and AK_start == 9999:
            spread = ((CL_ask[0]['price'] - pipeline_bid[0]['price']) * 10_000) - (pipeline_cost + 5000)
            print(f"spread: {round(spread)}, {pipeline} cost: {pipeline_cost}, CL_price: {CL_bid[0]['price']}, pipeline_price: {pipeline_bid[0]['price']}")
            if spread > threshold and not transporting_NYC:
                print("BUY AK-STORAGE AND TRANSPORT")
                storage_model.end_unused_storage(session)

                # Calculate how many lots we can buy (up to 10)
                max_lots = min((MAX_NET_POSITION - net_pos) // 10, 10)
                leased = safe_lease_storage(session, "AK-STORAGE", max_lots)
                offset = ensure_position_capacity(session, "BUY", leased)
                for _ in range(int(leased)):
                    helper.place_market_order(session, "CL-AK", "BUY", 10)
                lease_and_use_pipeline(session, pipeline, leased)
                AK_start = helper.get_tick(session, round)
                transporting_AK = True
                unwind_cl2f_offset(session, "BUY", offset)

        # CS → NYC
        elif pipeline == "CS-NYC-PIPE" and NY_start == 9999:
            spread = ((pipeline_ask[0]['price'] - CL_bid[0]['price']) * 10_000) - (pipeline_cost + 5000)
            print(f"spread: {round(spread)}, {pipeline} cost: {pipeline_cost}, CL_price: {CL_bid[0]['price']}, pipeline_price: {pipeline_bid[0]['price']}")
            if spread > threshold and not transporting_AK:
                print("BUY CL-STORAGE AND TRANSPORT CL TO NY")
                storage_model.end_unused_storage(session)

                max_lots = min((MAX_NET_POSITION - net_pos) // 10, 10)
                leased = safe_lease_storage(session, "CL-STORAGE", max_lots)
                offset = ensure_position_capacity(session, "BUY", leased)
                for _ in range(int(leased)):
                    helper.place_market_order(session, "CL", "BUY", 10)
                lease_and_use_pipeline(session, pipeline, leased)
                if leased > 0:
                    NY_start = helper.get_tick(session, round)
                    transporting_NYC = True
                unwind_cl2f_offset(session, "BUY", offset)

        # Arrival in CS from AK
        if pipeline == "AK-CS-PIPE" and helper.get_tick(session, round) > AK_start + 26:
            stor_count = storage_model.get_storage_count(session)
            for _ in range(int(10-stor_count)):
                storage_model.lease_storage(session, "CL-STORAGE")
            sleep(4)
            lots = int(helper.get_position(session, "CL") / 10)
            offset = ensure_position_capacity(session, "SELL", lots)
            for _ in range(int(lots)):
                helper.place_market_order(session, "CL", "SELL", 10)
            unwind_cl2f_offset(session, "SELL", offset)
            AK_start = 9999
            transporting_AK = False

        # Arrival in NYC from CS
        elif pipeline == "CS-NYC-PIPE" and helper.get_tick(session, round) > NY_start + 26:
            stor_count = storage_model.get_storage_count(session)
            for _ in range(int(10-stor_count)):
                storage_model.lease_storage(session, "NYC-STORAGE")
            sleep(4)
            lots = int(helper.get_position(session, "CL-NYC") / 10)
            offset = ensure_position_capacity(session, "SELL", lots)
            for _ in range(int(lots)):
                helper.place_market_order(session, "CL-NYC", "SELL", 10)
            unwind_cl2f_offset(session, "SELL", offset)
            NY_start = 9999
            transporting_NYC = False

    return AK_start, NY_start, transporting_AK, transporting_NYC


def lease_and_use_pipeline(session, pipeline, quantity_lots=10):
    for _ in range(int(quantity_lots)):
        session.post("http://localhost:9999/v1/leases", params={"ticker": pipeline})
        if pipeline == "AK-CS-PIPE":
            session.post("http://localhost:9999/v1/leases", params={"ticker": pipeline, "from1": "CL-AK", "quantity1": 10})
        elif pipeline == "CS-NYC-PIPE":
            session.post("http://localhost:9999/v1/leases", params={"ticker": pipeline, "from1": "CL", "quantity1": 10})

def safe_lease_storage(session, storage_name, desired_leases):
    current_leases = helper.get_storage_leases(session, storage_name)
    leases_remaining = max(0, 10 - current_leases)
    leases_to_make = min(leases_remaining, desired_leases)
    for _ in range(int(leases_to_make)):
        storage_model.lease_storage(session, storage_name)
    return leases_to_make

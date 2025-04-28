import helper
import storage_model
from time import sleep



def buy_refinery(session):
    """Leases a refinery."""
    resp = session.post('http://localhost:9999/v1/leases', params={'ticker': 'CL-REFINERY'})
    if resp.ok:
        print("Successfully leased refinery.")
    else:
        raise Exception(f"Error leasing refinery: {resp.text}")
    
def use_refinery(session):
    """Uses a leased refinery with 30 CL."""
    # Get current leases
    resp = session.get('http://localhost:9999/v1/leases', params={'ticker': 'CL-REFINERY'})
    leaseinfo = resp.json()
    # Find id of CL-REFINERY in list of leases
    for x in leaseinfo:
        if "CL-REFINERY" in x['ticker']:
            leaseid = x['id']
            session.post('http://localhost:9999/v1/leases/{}'.format(leaseid), params={'from1': 'CL', 'quantity1': 30})
            print("Successfully used refinery.")
            return True
    print("Refinery not found in leases.")
    return False

def decide_to_buy_refinery(session, start_tick, end_tick, time_refining, round, threshold_profit=100000, refinery_cost=300000):
    """Decides whether to buy the refinery based on expected profit"""
    try:
        CL_bid, CL_ask = helper.ticker_bid_ask(session, "CL")
        HO_bid, HO_ask = helper.ticker_bid_ask(session, "HO")
        RB_bid, RB_ask = helper.ticker_bid_ask(session, "RB")

        avg_CL = (CL_bid[0]['price'] + CL_ask[0]['price']) / 2
        avg_HO = (HO_bid[0]['price'] + HO_ask[0]['price']) / 2
        avg_RB = (RB_bid[0]['price'] + RB_ask[0]['price']) / 2

        profit = (10 * avg_HO * 42000) + (20 * avg_RB * 42000) - refinery_cost - (30 * avg_CL * 1000) - (3 * 500)

        print(f"Expected refinery profit: {profit:.2f}")

        if time_refining == 0: refinery_cost = 300000

        if profit > threshold_profit and start_tick == 0:
            if round == 1 or (round == 2 and 600 - helper.get_tick(session) > 55):
                print("Profitable! Buying and using refinery...")
                for _ in range(3):
                    storage_model.lease_storage(session, "CL-STORAGE")
                helper.place_market_order(session, "CL", "BUY", 30)
                helper.place_market_order(session, "CL-2F", "SELL", 30)
                buy_refinery(session)
                while not use_refinery(session):
                    sleep(0.05)
                time_refining += 1
                if round == 1 and helper.get_tick(session) > 555:
                    start_tick = helper.get_tick(session) - 600  # update start_tick here 
                    end_tick = start_tick + 45
                else:
                    start_tick = helper.get_tick(session)  # update start_tick here
                    end_tick = start_tick + 45
        elif start_tick != 0:
            tick = helper.get_tick(session)
            if tick < end_tick:
                if time_refining == 4:
                    refinery_cost = 0
                if time_refining == 3:
                    refinery_cost = 120000
                if time_refining == 2:
                    refinery_cost = 180000
                if time_refining == 1:
                    refinery_cost = 240000
            else:
                if profit < threshold_profit:
                    print("Not profitable! Selling refinery...")
                    end_lease_refinery(session)
                    helper.place_market_order(session, "CL-2F", "BUY", 30)
                    helper.place_market_order(session, "HO", "SELL", 10)
                    helper.place_market_order(session, "RB", "SELL", 20)
                    print(f"start tick should be reset to 0: {start_tick}")
                    time_refining = 0
                    start_tick = 0  # reset start_tick after selling refinery
                    end_tick = 0
                else:
                    if round == 1 or (round == 2 and 600 - helper.get_tick(session) > 55):
                        print("Refinery is still profitable. Keeping lease.")
                        for _ in range(3):
                            storage_model.lease_storage(session, "CL-STORAGE")
                        helper.place_market_order(session, "CL", "BUY", 30)
                        helper.place_market_order(session, "HO", "SELL", 10)
                        helper.place_market_order(session, "RB", "SELL", 20)
                        use_refinery(session)
                        if round == 1 and helper.get_tick(session) > 555:
                            start_tick = helper.get_tick(session) - 600  # update start_tick here 
                            end_tick = start_tick + 45
                        else:
                            start_tick = helper.get_tick(session)  # update start_tick here
                            end_tick = start_tick + 45
                        if time_refining == 4:
                            time_refining = 0
                        else:
                            time_refining += 1
                    else:
                        print("Not enough time to refine")
                        end_lease_refinery(session)
                        helper.place_market_order(session, "CL-2F", "BUY", 30)
                        helper.place_market_order(session, "HO", "SELL", 10)
                        helper.place_market_order(session, "RB", "SELL", 20)
                        time_refining = 0
                        start_tick = 0
                        end_tick = 0

        else:
            print("Not profitable. Holding off.")

    except Exception as e:
        print(f"Error during refinery decision-making: {e}")

    return start_tick, end_tick, refinery_cost, time_refining  # <- return the (possibly updated) start_tick

def end_lease_refinery(session):
    """Ends the refinery lease"""
    resp = session.get('http://localhost:9999/v1/leases')
    lease_info = resp.json()
    for x in lease_info:
        if x['containment_usage'] == 0:
            lease_id = x['id']
            session.delete('http://localhost:9999/v1/leases/{}'.format(lease_id))


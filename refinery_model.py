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

def decide_to_buy_refinery(session, start_tick, end_tick, time_refining, round, hedge, transporting_Ak, refinery_hedged, using_refinery, threshold_profit=-1000000, refinery_cost=300000):
    """Decides whether to buy the refinery based on expected profit"""
    CL_bid, CL_ask = helper.ticker_bid_ask(session, "CL")
    HO_bid, HO_ask = helper.ticker_bid_ask(session, "HO")
    RB_bid, RB_ask = helper.ticker_bid_ask(session, "RB")

    avg_CL = (CL_bid[0]['price'] + CL_ask[0]['price']) / 2
    avg_HO = (HO_bid[0]['price'] + HO_ask[0]['price']) / 2
    avg_RB = (RB_bid[0]['price'] + RB_ask[0]['price']) / 2

    profit = (10 * avg_HO * 42000) + (20 * avg_RB * 42000) - refinery_cost - (30 * avg_CL * 1000) - (3 * 500)

    print(f"Expected refinery profit: {profit:.2f}")

    if time_refining == 0: refinery_cost = 300000

    print(start_tick)
    if profit > threshold_profit and start_tick == 0:
        if round == 1 or (round == 2 and 1200 - helper.get_tick(session, round) > 55):
            print("Profitable! Buying and using refinery...")
    
            buy_refinery(session)
            refinery_hedged = how_much_CL_I_can_refine(session, hedge, refinery_hedged)
            using_refinery = True
            while not use_refinery(session):
                sleep(0.05)
            time_refining += 1
            start_tick = helper.get_tick(session, round)  # update start_tick here
            end_tick = start_tick + 45
    elif start_tick != 0:
        tick = helper.get_tick(session, round)
        if tick < end_tick:
            if time_refining == 4:
                refinery_cost = 260000
            if time_refining == 3:
                refinery_cost = 280000
            if time_refining == 2:
                refinery_cost = 280000
            if time_refining == 1:
                refinery_cost = 280000
        else:
            if profit < threshold_profit:
                print("Not profitable! Selling refinery...")
                end_lease_refinery(session)
                refinery_hedged = sell_refinery_positions(session, hedge, refinery_hedged)
                print(f"start tick should be reset to 0: {start_tick}")
                time_refining = 0
                start_tick = 0  # reset start_tick after selling refinery
                end_tick = 0   
                using_refinery = False

            else:
                if round == 1 or (round == 2 and 1200 - helper.get_tick(session, round) > 55):
                    print("Refinery is still profitable. Keeping lease.")
                    desired_lots = int(3 - (helper.get_position(session, "CL") / 10))
    
                    storage_model.end_unused_storage(session)

                    if desired_lots > 0:
                        # Check net position and free up room using CL-2F if needed
                        net_pos = helper.get_net_position(session)
                        cl2f_offset = 0
                        required_position = desired_lots * 10

                        if net_pos + required_position > 100:
                            excess = (net_pos + required_position) - 100
                            cl2f_offset = (excess + 9) // 10
                            for _ in range(int(cl2f_offset)):
                                helper.place_market_order(session, "CL-2F", "SELL", 10)

                        # Lease storage and buy CL
                        for _ in range(int(desired_lots)):
                            storage_model.lease_storage(session, "CL-STORAGE")
                            helper.place_market_order(session, "CL", "BUY", 10)

                        # Unwind CL-2F offset
                        for _ in range(int(cl2f_offset)):
                            helper.place_market_order(session, "CL-2F", "BUY", 10)
                    helper.place_market_order(session, "HO", "SELL", 10)
                    helper.place_market_order(session, "RB", "SELL", 20)
                    if hedge == False and refinery_hedged == True:
                        helper.place_market_order(session, "CL", "BUY", 30)
                        refinery_hedged = False
                    if hedge == True and refinery_hedged == False:
                        helper.place_market_order(session, "CL-2F", "SELL", 30)
                        refinery_hedged = True
                    use_refinery(session)
                    using_refinery = True
                    start_tick = helper.get_tick(session, round)  # update start_tick here
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
                    using_refinery = False

    else:
        print("Not profitable. Holding off.")


    return start_tick, end_tick, refinery_cost, time_refining, using_refinery, refinery_hedged  # <- return the (possibly updated) start_tick

def end_lease_refinery(session):
    """Ends the refinery lease"""
    resp = session.get('http://localhost:9999/v1/leases')
    lease_info = resp.json()
    for x in lease_info:
        if x['ticker'] == 'CL-REFINERY':
            lease_id = x['id']
            session.delete('http://localhost:9999/v1/leases/{}'.format(lease_id))
            

def how_much_CL_I_can_refine(session, hedge, refinery_hedged): 
   storage_model.end_unused_storage(session)
   net_pos = helper.get_net_position(session)
   if net_pos > 70:
       position = int((helper.get_position(session, "CL") / 10))
       order_quantity = 3- position
       helper.place_market_order(session, "CL-2F", "SELL", 30)
       if order_quantity > 0:
        for _ in range(int(order_quantity)):
            storage_model.lease_storage(session, "CL-STORAGE")
            helper.place_market_order(session, "CL", "BUY", 10)
   else:
        position = int((helper.get_position(session, "CL") / 10))
        order_quantity = 3- position
        if order_quantity > 0:
         for _ in range(int(order_quantity)):
            storage_model.lease_storage(session, "CL-STORAGE")
            helper.place_market_order(session, "CL", "BUY", 10)
        helper.place_market_order(session, "CL-2F", "SELL", 30)
   if hedge == False:
         helper.place_market_order(session, "CL-2F", "BUY", 30)
   else:
        return refinery_hedged == True
   
def sell_refinery_positions(session, hedge, refinery_hedged):
    net_pos = int(helper.get_net_position(session))
    if net_pos > -70:
        helper.place_market_order(session, "HO", "SELL", 10)
        helper.place_market_order(session, "RB", "SELL", 20)
    else:
        if net_pos > -80 and refinery_hedged == True:
            pass
    if refinery_hedged == False:
        pass
    else:
        refinery_hedged = False
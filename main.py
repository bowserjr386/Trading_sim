import helper
import signal
import requests
import storage_model
import refinery_model
from time import sleep
shutdown = False

def trading_loop(session):
    round = 1
    start_tick = 0
    end_tick = 0
    threshold_profit = 40000
    refinery_cost = 300000
    tick = helper.get_tick(session)
    time_refining = 0

    while True:
        if tick <= 600 and not shutdown:
            if round == 2 or (round == 1 and tick > 1):
                tick = helper.get_tick(session)
                valid = True
                print(f"start_tick: {start_tick}, threshold_profit: {threshold_profit}")
                try:
                    bid, ask = helper.ticker_bid_ask(session, "CL-1F")
                except Exception as e:
                    valid = False
                    round = 2
                if valid:
                    # storage_model.CL_future_arb(session, "CL-2F", tick, round)
                    # storage_model.CL_future_arb(session, "CL-1F", tick, round)
                    pass
                else:
                    pass
                    # storage_model.CL_future_arb(session, "CL-2F", tick, round)
                # HERE: update start_tick
                start_tick, end_tick, refinery_cost, time_refining = refinery_model.decide_to_buy_refinery(
                    session, start_tick, end_tick, time_refining, round, threshold_profit, refinery_cost)
                print(f"time_refining: {time_refining}")
                sleep(1)
                storage_model.end_unused_storage(session)
                

# Main entry point
def main():
    global shutdown
    signal.signal(signal.SIGINT, helper.signal_handler)
    with helper.create_session() as s:
        trading_loop(s)

if __name__ == '__main__':
    main()
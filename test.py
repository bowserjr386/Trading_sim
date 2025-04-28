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
    threshold_profit = -100000
    refinery_cost = 300000
    tick = helper.get_tick(session)

    while tick <= 600 and tick >= 2 and not shutdown:
        tick = helper.get_tick(session)
        valid = True
        print(f"start_tick: {start_tick}, threshold_profit: {threshold_profit}")
        
        

# Main entry point
def main():
    global shutdown
    signal.signal(signal.SIGINT, helper.signal_handler)
    with helper.create_session() as s:
        for _ in range(3):
            storage_model.lease_storage(s, "CL-STORAGE")
        helper.place_market_order(s, "CL", "BUY", 30)
        refinery_model.buy_refinery(s)
        sleep(.2)
        refinery_model.use_refinery(s)
        while True:
            storage_model.end_unused_storage(s)

if __name__ == '__main__':
    main()
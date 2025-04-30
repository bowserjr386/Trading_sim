import helper
import signal
import requests
import arb_NYC
import storage_model
import transport_model
import refinery_model
import news_model
from time import sleep
shutdown = False

def trading_loop(session):
    round = 1
    start_tick = 0
    end_tick = 0
    threshold_profit = 400000
    hedge = True
    refinery_cost = 300000
    tick = helper.get_tick(session, round)
    transporting_NYC = False
    transporting_AK = False
    news_id = 0
    news_end = 9999
    discrepancy = 0
    AK_start = 9999
    NY_start = 9999
    time_refining = 0
    using_refinery = False
    refinery_hedged = False

    while True:
        if tick <= 1200 and not shutdown:
            if round == 2 or (round == 1 and tick > 1):
                tick = helper.get_tick(session, round)
                valid = True
                #print(f"start_tick: {start_tick}, end_tick {end_tick}")
                try:
                    bid, ask = helper.ticker_bid_ask(session, "CL-1F")
                except Exception as e:
                    valid = False
                    round = 2 
                discrepancy, news_id, news_end = news_model.get_news(session, discrepancy, news_id, news_end)
                storage_model.CL_future_arb(session, "CL-2F", tick, round, hedge)
                # HERE: update start_tick
                start_tick, end_tick, refinery_cost, time_refining, refinery_hedged, using_refinery = refinery_model.decide_to_buy_refinery(
                    session, start_tick, end_tick, time_refining, round, hedge, transporting_AK, refinery_hedged, using_refinery, threshold_profit, refinery_cost)
                #print(f"time_refining: {time_refining}")
                AK_start, NY_start, transporting_AK, transporting_NYC = transport_model.decide_transport_arb(session,'AK-CS-PIPE', AK_start, NY_start, 
                                transporting_AK, transporting_NYC, hedge, using_refinery)
                AK_start, NY_start, transporting_AK, transporting_NYC = transport_model.decide_transport_arb(session,'CS-NYC-PIPE', AK_start, NY_start, 
                                transporting_AK, transporting_NYC, hedge, using_refinery)
                arb_NYC.trade_CL_NYC(session)
                storage_model.end_unused_storage(session)
                sleep(1)
            else:
                tick = helper.get_tick(session, round)
                

# Main entry point
def main():
    global shutdown
    signal.signal(signal.SIGINT, helper.signal_handler)
    with helper.create_session() as s:
        trading_loop(s)

if __name__ == '__main__':
    main()
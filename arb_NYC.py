import helper
import storage_model
from time import sleep

def trade_CL_NYC(session):
    """
    Implements CL-NYC trading strategy:
    - Buy CL-NYC (100) if CL-NYC-CL spread < 1.90
    - Sell CL-NYC if CL-NYC-CL spread >= 2.00
    - Hedge CL-NYC positions with CL-2F
    """
    try:
        # Get current positions
        cl_nyc_position = helper.get_position(session, "CL-NYC")
        cl_2f_position = helper.get_position(session, "CL-2F")
        
        # Get current prices
        CL_bid, CL_ask = helper.ticker_bid_ask(session, "CL")
        CL_NYC_bid, CL_NYC_ask = helper.ticker_bid_ask(session, "CL-NYC")
        CL_2F_bid, CL_2F_ask = helper.ticker_bid_ask(session, "CL-2F")
        
        if CL_bid is not None and CL_NYC_bid is not None and CL_2F_bid is not None:
            # Calculate spreads
            cl_nyc_spread = CL_NYC_bid[0]['price'] - CL_ask[0]['price']
            
            print(f"Hold NYC if spread less than 1.90: {cl_nyc_spread:.2f}")
            
            # # Trading logic
            # if cl_nyc_spread < 1.70 and cl_nyc_position == 0:
            #     # Buy CL-NYC and hedge with CL-2F
            #     print("Buying CL-NYC and hedging with CL-2F")
            #     for _ in range(10):
            #         storage_model.lease_storage(session, "NYC-STORAGE")
            #         helper.place_market_order(session, "CL-NYC", "BUY", 10)
            #         helper.place_market_order(session, "CL-2F", "SELL", 10)
                
            # elif cl_nyc_spread >= 2.00 and cl_nyc_position > 0:
            #     # Sell CL-NYC and close hedge
            #     print("Selling CL-NYC and closing hedge")
            #     for _ in range(10):
            #         helper.place_market_order(session, "CL-NYC", "SELL", 10)
            #         helper.place_market_order(session, "CL-2F", "BUY", 10)
                
    except Exception as e:
        print(f"Error in CL-NYC trading: {e}")

def trading_loop(session):
    """
    Main trading loop for CL-NYC strategy
    """
    while True:
        try:
            trade_CL_NYC(session)
            sleep(1)  # Wait 1 second between iterations
        except Exception as e:
            print(f"Error in trading loop: {e}")
            sleep(1)
            storage_model.end_unused_storage(session)

if __name__ == "__main__":
    with helper.create_session() as s:
        trading_loop(s)

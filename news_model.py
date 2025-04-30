import re
import helper
import storage_model

def get_news(session, discrepancy, news_id, news_end):
    """Fetches the latest news from the RIT API."""
    try:
        resp = session.get('http://localhost:9999/v1/news')
        if resp.ok:
            news_items = resp.json()
            #print(news_items)

        else:
            print(f"Error fetching news: {resp.text}")
            return []
    except Exception as e:
        print(f"Exception while fetching news: {e}")
        return []
    if news_id != news_items[0]["news_id"] and news_end == 9999:
        news_id = news_items[0]["news_id"]
        headline = (news_items[0]['headline'])
        print(headline)
        discrepancy = int(parse_discrepancy(headline))
        if discrepancy:
            news_end = helper.get_tick(session, round) + 20
    if discrepancy > 3:
        if helper.get_tick(session, round) > news_end:
            discrepancy = 0
            offload_cl2f_position(session)
            news_end = 9999
        else:
            print(f"CL is going up {discrepancy*.1}")
            helper.try_to_order(session, "CL-2F", "BUY", "100")
            # storage = storage_model.get_storage_count(session)
            # order = 10 - storage
            # for _ in range(int(order)):
            #     storage_model.lease_storage(session, "CL")
            #     helper.place_market_order(session, "CL", "BUY", 10)
    if discrepancy < -3:
        if helper.get_tick(session, round) > news_end:
            discrepancy = 0
            news_end = 9999
            offload_cl2f_position(session)
        else:
            print(f"CL is going down {discrepancy*.1}")
            helper.try_to_order(session, "CL-2F", "SELL", "100")
            
    return discrepancy, news_id, news_end
    

def parse_discrepancy(report_str):
    report_str = report_str.upper()

    # Check that both 'ACTUAL' and 'FORECAST' are in the string
    if 'ACTUAL' not in report_str or 'FORECAST' not in report_str:
        return 0  # Or raise an error, or return 0, depending on your needs

    # Extract (ACTUAL|FORECAST), (DRAW|BUILD)?, amount
    matches = re.findall(r'(ACTUAL|FORECAST)\s+(DRAW|BUILD)?\s*(\d+)\s*MLN\s*BBLS', report_str)

    values = {'ACTUAL': None, 'FORECAST': None}

    for kind, change_type, amount_str in matches:
        amount = int(amount_str)
        signed_amount = amount if change_type == 'DRAW' or change_type is None else -amount
        values[kind] = signed_amount

    if values['ACTUAL'] is None or values['FORECAST'] is None:
        return 0  # In case both terms are present but one value is missing

    discrepancy = values['ACTUAL'] - values['FORECAST']
    return discrepancy

def offload_cl2f_position(session):
    position = helper.get_position(session, "CL-2F")

    if position > 0:
        print(f"Offloading LONG CL-2F position: {position}")
        for _ in range(int(position // 10)):
            helper.place_market_order(session, "CL-2F", "SELL", 10)
    elif position < 0:
        print(f"Offloading SHORT CL-2F position: {abs(position)}")
        for _ in range(int(abs(position) // 10)):
            helper.place_market_order(session, "CL-2F", "BUY", 10)
    else:
        print("No CL-2F position to offload.")



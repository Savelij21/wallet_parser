import operator


def sorting_by_earning(tickers):
    ticker_price_pairs = []

    for ticker in tickers.keys():
        sum_delta = float(tickers[ticker]['sum_delta_usd']) if tickers[ticker]['sum_delta_usd'] != 'N/A' else -999999.9
        ticker_price_pairs.append(
            {
                'ticker_name': ticker,
                'sum_delta_usd': sum_delta
            }
        )

    ticker_price_pairs.sort(key=operator.itemgetter('sum_delta_usd'))

    sorted_tickers = []
    for ticker in ticker_price_pairs:
        sorted_tickers.append(tickers[ticker['ticker_name']])

    return sorted_tickers


    # sorted_tickers_by_earn_sum = sorted(
    #     ticker_price_pairs,
    #     key=lamda ticker_price_pairs: ticker_price_pairs['ticker']
    # )

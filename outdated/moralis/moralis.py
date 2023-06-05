import requests, json

# my test key eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJub25jZSI6ImI0NWJiZTNjLWE0Y2ItNDVkMS1iOTNjLTE0MmFmNDhkODc0OSIsIm9yZ0lkIjoiMzM3MTg3IiwidXNlcklkIjoiMzQ2NjY1IiwidHlwZUlkIjoiZjI5MjRhNGYtNmM5Zi00NWU0LTkzNzYtNDhhYjVjZmZlZTgwIiwidHlwZSI6IlBST0pFQ1QiLCJpYXQiOjE2ODQ5OTk3MDgsImV4cCI6NDg0MDc1OTcwOH0.mTjW_bunzdVAnMg6M5-cke8v5n0IP0obs0KEYR6-vuE
# payed pro key: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJub25jZSI6IjljNmYyYTNjLTQ3ZWYtNGUzZi1hMjA1LWI4MGQxOTRmYTUyZCIsIm9yZ0lkIjoiMzM3MjgwIiwidXNlcklkIjoiMzQ2NzYyIiwidHlwZUlkIjoiZDJlY2FhZWUtZTM5Ny00NWI0LWFlMDEtOWU1MjBlMDc5NTFhIiwidHlwZSI6IlBST0pFQ1QiLCJpYXQiOjE2ODUwMTc0ODAsImV4cCI6NDg0MDc3NzQ4MH0.kgyhFF4BeZkBminxaVdYzBv9ZGCtDysvQcZNT-Qul9w

moralis_api_key = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJub25jZSI6IjljNmYyYTNjLTQ3ZWYtNGUzZi1hMjA1LWI4MGQxOTRmYTUyZCIsIm9yZ0lkIjoiMzM3MjgwIiwidXNlcklkIjoiMzQ2NzYyIiwidHlwZUlkIjoiZDJlY2FhZWUtZTM5Ny00NWI0LWFlMDEtOWU1MjBlMDc5NTFhIiwidHlwZSI6IlBST0pFQ1QiLCJpYXQiOjE2ODUwMTc0ODAsImV4cCI6NDg0MDc3NzQ4MH0.kgyhFF4BeZkBminxaVdYzBv9ZGCtDysvQcZNT-Qul9w'


def transactions_prices(transactions):
    for transaction in transactions:
        # test
        # if transaction['tokenSymbol'] not in ['K9', 'Ok4mi', 'Circle', 'DOGSHI', 'PARTY', 'DRIP']:
        #     continue

        transaction['token_price_usd'] = get_token_price(
            token_address=transaction['contractAddress'],
            block_number=transaction['blockNumber']
        )
        transaction['sum_usd'] = transaction['value'] * transaction['token_price_usd'] if transaction['token_price_usd'] != 'N/A' else 'N/A'

        # test
        print(f'{transaction["tokenSymbol"]} price in USD: {transaction["token_price_usd"]}')

    return transactions


def get_token_price(token_address, x_api_key=moralis_api_key, block_number=None):
    api_url = 'https://deep-index.moralis.io/api/v2/erc20'

    if not block_number:
        response = requests.get(
            url=api_url + f'/{token_address}/price?chain=eth',
            headers={
                'X-API-Key': x_api_key
            },
            timeout=3000
        )
    else:
        response = requests.get(
            url=api_url + f'/{token_address}/price',
            headers={
                'X-API-Key': x_api_key
            },
            params={
                'chain': 'eth',
                'to_block': block_number
            },
            timeout=3000
        )

    if response.status_code != 200:
        return 'N/A'

    return response.json()['usdPrice']


def get_ticker_price_and_sum_metrics(ticker):
    # test
    address = ticker['transactions'][0]['contractAddress']
    ticker['current_price_usd'] = get_token_price(token_address=address)

    if ticker['current_price_usd'] != 'N/A':
        ticker['total_delta_usd'] = ticker['total_delta'] * ticker['current_price_usd']
    else:
        ticker['total_delta_usd'] = 'N/A'

    for transaction in ticker['transactions']:
        if transaction['type'] == 'buying':
            if transaction['sum_usd'] != 'N/A' and ticker['sum_bought_usd'] != 'N/A':
                ticker['sum_bought_usd'] += transaction['sum_usd']
            else:
                ticker['sum_bought_usd'] = 'N/A'

        else:
            if transaction['sum_usd'] != 'N/A' and ticker['sum_sold_usd'] != 'N/A':
                ticker['sum_sold_usd'] += transaction['sum_usd']
            else:
                ticker['sum_sold_usd'] = 'N/A'

    if ticker['sum_sold_usd'] == 'N/A' or ticker['sum_bought_usd'] == 'N/A':
        ticker['sum_delta_usd'] = 'N/A'
    else:
        ticker['sum_delta_usd'] = ticker['sum_sold_usd'] - ticker['sum_bought_usd']

    print(f'Total delta in USD {ticker["total_delta_usd"]}')

import requests
from datetime import datetime
import json


# requesting data from API's ###################################
def get_transactions(api_url, wallet_address, api_key) -> list:
    params = {
        'module': 'account',
        'action': 'tokentx',
        'address': wallet_address,
        'apikey': api_key,
        'startblock': 0,
        'endblock': 99999999,
        'sort': 'desc',
        # 'page': 1,
        # 'offset': 20
    }

    response = requests.get(api_url, params=params).json()
    transactions: list = response['result']
    return transactions


# only ERC20 now
def etherscan_get_transactions(wallet_address, api_key):
    api_url = 'https://api.etherscan.io/api'

    return get_transactions(api_url=api_url, wallet_address=wallet_address, api_key=api_key)


# BEP-20 only now
def bscscan_get_transactions(wallet_address, api_key):
    api_url = 'https://api.bscscan.com/api'

    return get_transactions(api_url=api_url, wallet_address=wallet_address, api_key=api_key)


##################################


def edit_transaction_fields(transactions: list, wallet_address) -> list:
    updated_transactions = []
    for transaction in transactions:
        # adding field - type of transaction (buy/sell)
        if transaction['from'] == wallet_address:
            transaction['type'] = 'selling'
        else:
            transaction['type'] = 'buying'

        # transform 'value' field to understood view
        transaction['raw_value'] = int(transaction['value'])
        transaction['value'] = convert_value(
            value=transaction['value'],
            decimal=int(transaction['tokenDecimal'])
        )

        # adding 'date_time' and 'time_since' fields
        date_time = datetime.utcfromtimestamp(int(transaction['timeStamp']))
        transaction['date_time'] = str(date_time)
        transaction['time_since'] = str(datetime.utcnow() - date_time)

        # adding 'price' fields for every transaction
        transaction['token_price_usd'] = 'N/A'
        transaction['sum_usd'] = 0

        # deleting unused fields
        # del transaction['blockNumber']
        # del transaction['timeStamp']
        del transaction['nonce']
        del transaction['blockHash']
        del transaction['from']
        # del transaction['contractAddress']
        del transaction['to']
        # del transaction['tokenDecimal']
        del transaction['transactionIndex']
        del transaction['gas']
        del transaction['gasPrice']
        del transaction['gasUsed']
        del transaction['cumulativeGasUsed']
        del transaction['input']
        del transaction['confirmations']

        updated_transactions.append(transaction)

    return updated_transactions


def grouping_transactions_by_ticker(transactions: list) -> dict:
    grouped_transactions = {}
    for transaction in transactions:
        ticker = transaction['tokenSymbol']

        # creating detailed dict for ticker
        if ticker in grouped_transactions.keys():
            grouped_transactions[ticker]['transactions'].append(transaction)
        else:
            grouped_transactions[ticker] = {
                'transactions': [transaction],

                'total_bought': 0,  # amount of bought tokens (a lot)
                'total_sold': 0,  # amount of sold tokens (a lot)
                'total_delta': 0,  # amount delta (a lot)
                'total_delta_usd': 0,  # amount delta in $ for current moment ($)

                'sum_bought_usd': 0,  # sum of buy transactions ($)
                'sum_sold_usd': 0,  # sum of sell transactions ($)
                'sum_delta_usd': 0,  # delta of buy and sel sums ($)

                'current_price_usd': 0,

                'buying_amount': 0,  # amount of buy transactions (a lot)
                'selling_amount': 0,  # amount of sell transactions (a lot)
            }

    # calculating metrics
    for ticker in grouped_transactions.keys():
        ticker_details = grouped_transactions[ticker]
        ticker_details['transactions'] = remove_splits(ticker_details)
        calc_total_metrics(ticker_details)
        calc_sum_metrics(ticker_details)
        calc_transactions_amount(ticker_details)

    return grouped_transactions


# calculating ticker's metrics
def calc_total_metrics(ticker):

    for transaction in ticker['transactions']:
        if transaction['type'] == 'buying':
            ticker['total_bought'] += transaction['value']
        else:
            ticker['total_sold'] += transaction['value']

    ticker['total_delta'] = ticker['total_bought'] - ticker['total_sold']
    ticker['total_delta_usd'] = 0  # calc with current token price !


def calc_sum_metrics(ticker):
    pass  # calc sum for every tran-ion and then sum these values


def calc_transactions_amount(ticker):

    for transaction in ticker['transactions']:
        if transaction['type'] == 'buying':
            ticker['buying_amount'] += 1
        else:
            ticker['selling_amount'] += 1


# support functions
def remove_splits(ticker):
    non_split_transactions = []
    orig_hashes = []
    for transaction in ticker['transactions']:
        if transaction['hash'] not in orig_hashes:
            non_split_transactions.append(transaction)
            orig_hashes.append(transaction['hash'])
        else:
            for i in non_split_transactions:
                if i['hash'] == transaction['hash']:
                    i['raw_value'] += transaction['raw_value']

    for transaction in non_split_transactions:
        transaction['value'] = convert_value(
            value=str(transaction['raw_value']),
            decimal=int(transaction['tokenDecimal'])
        )
        del transaction['tokenDecimal']

    return non_split_transactions


def convert_value(value, decimal):
    if len(value) < decimal:
        while len(value) < decimal:
            value = '0' + value

    first_part = len(value) - decimal
    new_value = float(value[:first_part] + '.' + value[first_part:])
    return new_value

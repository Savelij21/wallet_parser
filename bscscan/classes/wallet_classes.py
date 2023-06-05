import asyncio
import json

import aiohttp as aiohttp
import requests
from datetime import datetime
from typing import List
from bscscan.classes import mixins


class Wallet(mixins.APIKeys):

    def __init__(self, address, start_date, end_date, show_details):
        super().__init__()
        self.wallet_address = address
        self.start_date = start_date
        self.end_date = end_date
        self.show_details = show_details
        self.transactions: List['Transaction'] = self.__get_wallet_transactions()#[4:14]
        self.tickers: List['Ticker'] = self.__get_tickers()
        self.__sorting_tickers_by_sum_delta()
        self.__getting_24h_volume_usd_from_dexguru_for_tickers()

    # get wallet transactions from Bscscan API
    def __get_wallet_transactions(self) -> List['Transaction']:  # TODO: diff
        def bscscan_get_transactions() -> list:
            api_url = 'https://api.bscscan.com/api'

            params = {
                'module': 'account',
                'action': 'tokentx',
                'address': self.wallet_address,
                'apikey': self.bscscan_api_key,
                'startblock': 0,
                'endblock': 999999999,
                'sort': 'desc',
                # For testing BUSD (Peg) Token
                # 'contractaddress': '0xe9e7cea3dedca5984780bafc599bd69add087d56',
                # 'page': 1,
                # 'offset': 20
            }

            response = requests.get(api_url, params=params).json()
            raw_transactions: list = response['result']

            # tests
            # print(json.dumps(raw_transactions, indent=2))

            transactions = []
            for raw_transaction in raw_transactions:
                transaction = Transaction(raw_transaction, self.wallet_address)
                # filtering by date
                if self.start_date <= transaction.date_time <= self.end_date:
                    transactions.append(transaction)

            print(f'Found {len(transactions)} splited transactions in range {self.start_date} and {self.end_date}')

            def remove_splits(splited_transactions: List['Transaction']):
                non_split_transactions = []
                orig_hashes = []
                for transaction in splited_transactions:
                    if transaction._raw_transaction['hash'] not in orig_hashes:
                        non_split_transactions.append(transaction)
                        orig_hashes.append(transaction._raw_transaction['hash'])
                    else:
                        for i in non_split_transactions:
                            if i._raw_transaction['hash'] == transaction._raw_transaction['hash']:
                                i.value += transaction.value

                return non_split_transactions

            transactions = remove_splits(transactions)

            print(f'Found {len(transactions)} transactions in range {self.start_date} and {self.end_date}')
            return transactions

        return bscscan_get_transactions()

    # get wallet tickers (grouped transactions by token symbol)
    def __get_tickers(self) -> List['Ticker']:
        # prepare dict
        grouped_transactions = {}

        for transaction in self.transactions:
            if transaction.token_address in grouped_transactions.keys():
                grouped_transactions[transaction.token_address].append(transaction)
            else:
                grouped_transactions[transaction.token_address] = [transaction]

        # for transaction in self.transactions:
        #     if transaction.token_symbol in grouped_transactions.keys():
        #         grouped_transactions[transaction.token_symbol].append(transaction)
        #     else:
        #         grouped_transactions[transaction.token_symbol] = [transaction]

        # collecting Ticker objects
        tickers = []
        for token_address, transactions_list in grouped_transactions.items():
            tickers.append(Ticker(token_address, transactions_list))
        # reversing to get firstly old operations
        tickers.reverse()

        return tickers

    # sorting tickers list by sum_delta_usd param
    def __sorting_tickers_by_sum_delta(self):
        # handling tickers with invalid data and stablecoins
        stables = {}
        for ticker in self.tickers:
            if ticker.sum_delta_usd == 'N/A':
                ticker.sum_delta_usd = -999999999999999.9
            if ticker.is_stablecoin:
                stables[ticker.ticker_symbol] = ticker.sum_delta_usd
                ticker.sum_delta_usd = 999999999999999.9

        # sorting
        self.tickers.sort(key=lambda x: x.sum_delta_usd, reverse=True)

        # reversing invalid data for tickers
        for ticker in self.tickers:
            if ticker.sum_delta_usd == -999999999999999.9:
                ticker.sum_delta_usd = 'N/A'
            if ticker.is_stablecoin:
                ticker.sum_delta_usd = stables[ticker.ticker_symbol]

    # getting 24h volume in usd (to check scam)
    def __getting_24h_volume_usd_from_dexguru_for_tickers(self):  # TODO: diff
        async def get_volume_from_dexguru(tickers: List['Ticker']):
            async def assign_price_for_transaction(async_session, token_address):

                async with async_session.get(
                        url=f'https://api.dev.dex.guru/v1/chain/56/tokens/{token_address}/market',
                        headers={'api-key': self.dexguru_api_key},
                        timeout=3000
                ) as resp:
                    json_response = await resp.json()
                    return json_response

            async with aiohttp.ClientSession() as session:
                tasks = []
                for ticker in tickers:
                    tasks.append(asyncio.ensure_future(assign_price_for_transaction(
                        async_session=session,
                        token_address=ticker.token_address
                    )))

                responses = await asyncio.gather(*tasks)
                for k in range(len(tickers)):
                    if 'volume_24h_usd' not in responses[k].keys():
                        tickers[k].volume_24h_usd = 'N/A'
                    else:
                        tickers[k].volume_24h_usd = float(responses[k]['volume_24h_usd'])

        ##############################################
        if len(self.tickers) > 3:
            parts = []
            # grouping by 6 trans
            start = 0
            end = len(self.tickers)
            step = 3
            for i in range(start, end, step):
                parts.append(self.tickers[i:i + step])

            for part in parts:
                asyncio.run(get_volume_from_dexguru(part))

        else:
            asyncio.run(get_volume_from_dexguru(self.tickers))


class Transaction:

    def __init__(self, raw_transaction: dict, wallet_address):
        self._raw_transaction = raw_transaction
        self.token_symbol = self._raw_transaction['tokenSymbol']
        self.token_full_name = self._raw_transaction['tokenName']
        self.block_number = self._raw_transaction['blockNumber']
        self.token_address = self._raw_transaction['contractAddress']
        self.date_time = self.__get_transaction_date_time()
        self.value = self.__get_value()
        self.token_price_usd = 0
        self.sum_usd = 0

        if self._raw_transaction['to'].lower() == wallet_address.lower():
            self.type = 'buying'
        else:
            self.type = 'selling'

    def __str__(self):
        return self.token_symbol

    def __get_transaction_date_time(self):
        date_time = datetime.utcfromtimestamp(int(self._raw_transaction['timeStamp']))
        # transaction['time_since'] = str(datetime.utcnow() - date_time)
        return str(date_time)

    def __get_value(self):
        value = self._raw_transaction['value']
        decimal = int(self._raw_transaction['tokenDecimal'])
        if len(value) < decimal:
            while len(value) < decimal + 1:
                value = '0' + value

        first_part = len(value) - decimal
        new_value = float(value[:first_part] + '.' + value[first_part:])
        return new_value


class Ticker(mixins.APIKeys):

    def __init__(self, token_address, transactions: List[Transaction]):
        super().__init__()  # to get api key from Moralis mixin
        self.ticker_symbol = transactions[0].token_symbol
        self.full_ticker_name = transactions[0].token_full_name
        self.transactions = list(reversed(transactions))  # reverse is to sort transactions from old to new
        self.token_address = token_address
        self.total_bought = 0  # a lot of bought tokens (th)
        self.total_sold = 0  # a lot of sold tokens (th)
        self.total_delta = 0  # a lot of amount tokens delta
        self.total_delta_usd = 0  # tokens delta in USD
        self.sum_bought_usd = 0  # bought tokens in USD
        self.sum_sold_usd = 0  # sold tokens in USD
        self.sum_delta_usd = 0  # sums delta in USD (earning)
        self.current_price_usd = 0  # current token price in USD
        self.buy_tr_amount = 0  # a lot of 'buy' transactions
        self.sell_tr_amount = 0  # a lot of 'sell' transactions
        self.volume_24h_usd = 0  # volume for checking scam tokens
        self.is_valid = True  # if ticker have at least one N/A data - give False valid
        # stablecoin status check
        if self.ticker_symbol in self.stablecoins_list:
            self.is_stablecoin = True
        else:
            self.is_stablecoin = False  # is this token a stablecoin

        # GETTING TOKEN PRICES
        self.__get_historical_token_prices_from_moralis()
        self.__get_missing_historical_prices_from_dexguru()
        self.__get_actual_token_price_from_moralis()
        self.__get_missing_actual_price_from_dexguru()
        # CALCULATING PARAMS
        self.__calc_total_and_tr_amount_params()
        self.__calc_sum_params_and_usd_delta()

    # 1. GETTING TOKEN PRICES #########################################################################################
    #     1.1 getting historical prices from Moralis API
    def __get_historical_token_prices_from_moralis(self):
        if len(self.transactions) > 6:  # moralis api is limited by 6 requests per second
            parts = []
            # grouping by 6 trans
            start = 0
            end = len(self.transactions)
            step = 6
            for i in range(start, end, step):
                parts.append(self.transactions[i:i + step])

            for part in parts:
                asyncio.run(self.__async_get_prices_from_moralis_v2(part))

        else:
            asyncio.run(self.__async_get_prices_from_moralis_v2(self.transactions))

    async def __async_get_prices_from_moralis_v2(self, transactions: List[Transaction]):

        async def assign_price_for_transaction(async_session, token_address, block_number):  # TODO: diff
            api_url = 'https://deep-index.moralis.io/api/v2/erc20'

            async with async_session.get(
                    url=api_url + f'/{token_address}/price',
                    headers={'X-API-Key': self.moralis_api_key},
                    params={
                        'chain': 'bsc',
                        'to_block': block_number
                    },
                    timeout=3000
            ) as resp:
                json_price = await resp.json()
                return json_price

        async with aiohttp.ClientSession() as session:
            tasks = []
            for transaction in transactions:
                tasks.append(asyncio.ensure_future(assign_price_for_transaction(
                    async_session=session,
                    token_address=transaction.token_address,
                    block_number=transaction.block_number
                )))

            responses = await asyncio.gather(*tasks)
            for i in range(len(responses)):
                if 'usdPrice' not in responses[i].keys() or not responses[i]['usdPrice'] == 'NaN':  # TODO: add to eth
                    transactions[i].token_price_usd = 'Moralis can\'t find price'
                else:
                    transactions[i].token_price_usd = float(responses[i]['usdPrice'])

    #     1.2 getting missing historical prices for transactions with DexGuru
    def __get_missing_historical_prices_from_dexguru(self):  # TODO: diff
        # preparing request
        def __get_price_from_dexguru_by_timestamp_range(token_address, begin: int, end: int):
            dexguru_response = requests.get(
                url=f'https://api.dev.dex.guru/v1/chain/56/tokens/{token_address}/market/history',
                headers={
                    'api-key': self.dexguru_api_key
                },
                params={
                    'begin_timestamp': begin,
                    'end_timestamp': end
                }
            )
            return dexguru_response

        # implement
        for transaction in self.transactions:
            if transaction.token_price_usd == 'Moralis can\'t find price':
                begin_ts = int(transaction._raw_transaction['timeStamp'])
                end_ts = int(transaction._raw_transaction['timeStamp'])
                # TODO: will be diff from eth
                response = __get_price_from_dexguru_by_timestamp_range(
                    token_address=transaction.token_address,
                    begin=begin_ts,
                    end=end_ts
                )
                response_json = response.json()

                if response.status_code != 200:
                    print(transaction.token_symbol, transaction._raw_transaction['hash'], 'NOT 200')
                    transaction.token_price_usd = 'N/A'
                    self.is_valid = False
                elif response_json['total'] == 0:  # TODO: will be diff from eth
                    response = __get_price_from_dexguru_by_timestamp_range(
                        token_address=transaction.token_address,
                        begin=begin_ts-500000,
                        end=end_ts+500000
                    )
                    response_json = response.json()
                    if response.status_code != 200:
                        print(transaction.token_symbol, transaction._raw_transaction['hash'], 'NOT 200')
                        transaction.token_price_usd = 'N/A'
                        self.is_valid = False
                    elif response_json['total'] == 0:
                        print(transaction.token_symbol, transaction.token_full_name, 'no data in dexguru')
                        transaction.token_price_usd = 'N/A'
                        self.is_valid = False
                    else:
                        last_timestamp = 0
                        for i in range(len(response_json['data'])):
                            if (int(response_json['data'][i]['timestamp']) - int(transaction._raw_transaction['timeStamp'])) < abs(last_timestamp - int(transaction._raw_transaction['timeStamp'])):
                                last_timestamp = int(response_json['data'][i]['timestamp'])
                                transaction.token_price_usd = float(response_json['data'][i]['price_usd'])

                else:
                    transaction.token_price_usd = float(response_json['data'][0]['price_usd'])

    #     1.3 getting actual price from Moralis API (current_price_usd)
    def __get_actual_token_price_from_moralis(self):  # TODO: diff
        def get_price_from_moralis(token_address):
            api_url = 'https://deep-index.moralis.io/api/v2/erc20'
            response = requests.get(
                url=api_url + f'/{token_address}/price',
                headers={'X-API-Key': self.moralis_api_key},
                params={
                    'chain': 'bsc',
                },
                timeout=3000
            )
            if response.status_code != 200 or not response.json()['usdPrice'] == 'NaN':  # TODO: add to eth
                return 'Moralis can\'t find price'
            else:
                usd_price = float(response.json()['usdPrice'])
                return usd_price

        self.current_price_usd = get_price_from_moralis(self.token_address)

    #     1.4 getting missing actual price with DexGuru
    def __get_missing_actual_price_from_dexguru(self):  # TODO: diff
        def get_current_price_from_dexguru(token_address):
            dexguru_response = requests.get(
                url=f'https://api.dev.dex.guru/v1/chain/56/tokens/{token_address}/market',
                headers={
                    'api-key': self.dexguru_api_key
                }
            )
            response_json = dexguru_response.json()

            if dexguru_response.status_code != 200:
                print(self.ticker_symbol, 'getting actual price: NOT 200')
                self.is_valid = False
                return 'N/A'
            elif 'price_usd' not in response_json.keys():
                print(self.ticker_symbol, 'getting actual price: error in json')
                self.is_valid = False
                return 'N/A'

            current_usd_price = float(response_json['price_usd'])
            return current_usd_price

        self.current_price_usd = get_current_price_from_dexguru(self.token_address)

    ###################################################################################################################

    # 2. CALCULATING PARAMS ###########################################################################################
    #     2.1 calculating total_bought, total_sold, total_delta params, amount of buy/sell transactions
    def __calc_total_and_tr_amount_params(self):
        for transaction in self.transactions:
            if transaction.type == 'buying':
                self.total_bought += transaction.value
                self.buy_tr_amount += 1
            else:
                self.total_sold += transaction.value
                self.sell_tr_amount += 1

        self.total_delta = self.total_bought - self.total_sold

    #     2.2 calculating total_delta_usd, sum_bought_usd, sum_sold_usd, sum_delta_usd
    def __calc_sum_params_and_usd_delta(self):
        # total_delta_usd
        if self.is_valid:  # TODO: add the same check for eth
            self.total_delta_usd = self.total_delta * self.current_price_usd
            # if delta is too small -> down to zero
            if self.total_delta_usd < 1:
                self.total_delta = 0
                self.total_delta_usd = 0
        else:
            self.total_delta_usd = 'N/A'
        # sums for every transaction and collecting sum_bought and sum_sold
        for transaction in self.transactions:
            # 2.2.1 calculating sums for every transaction of ticker
            if transaction.token_price_usd != 'N/A':
                transaction.sum_usd = transaction.value * transaction.token_price_usd
            else:
                transaction.sum_usd = 'N/A'

            # 2.2.2 summing for bought and sold operations
            if self.is_valid:
                if transaction.type == 'buying':
                    self.sum_bought_usd += transaction.sum_usd
                else:
                    self.sum_sold_usd += transaction.sum_usd

            else:
                self.sum_bought_usd = 'N/A'
                self.sum_sold_usd = 'N/A'

        # sum_delta calc
        if self.is_valid:
            self.sum_delta_usd = self.sum_sold_usd - self.sum_bought_usd + self.total_delta_usd
        else:
            self.sum_delta_usd = 'N/A'
            # tests
            print(f'{self.ticker_symbol} is not valid')

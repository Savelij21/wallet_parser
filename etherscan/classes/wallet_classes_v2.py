import asyncio
import json

import aiohttp as aiohttp
import requests
from datetime import datetime
from typing import List
from etherscan.classes import mixins


class Wallet(mixins.APIKeys):

    def __init__(self, address, start_date, end_date, show_details):
        super().__init__()
        self.wallet_address = address
        self.start_date = start_date
        self.end_date = end_date
        self.show_details = show_details
        self.transactions: List['Transaction'] = self.__get_wallet_transactions()[0:10]
        self.tickers: List['Ticker'] = self.__get_tickers()

        self.__sorting_tickers_by_sum_delta()
        self.__checking_scam_by_volume_and_liquid_by_data_from_dexguru_for_tickers()

    # get wallet transactions from Etherscan API
    def __get_wallet_transactions(self) -> List['Transaction']:
        def etherscan_get_transactions() -> list:
            api_url = 'https://api.etherscan.io/api'

            params = {
                'module': 'account',
                'action': 'tokentx',
                'address': self.wallet_address,
                'apikey': self.etherscan_api_key,
                'startblock': 0,
                'endblock': 99999999,
                'sort': 'desc',
                # 'page': 1,
                # 'offset': 20
                # tests UNI-V2
                # 'contractaddress': '0x34b6f33a5d88fca1b8f78a510bc81673611a68f0'
            }

            response = requests.get(api_url, params=params).json()
            raw_transactions: list = response['result']

            transactions = []
            for raw_transaction in raw_transactions:

                transaction = Transaction(raw_transaction, self.wallet_address)

                # filtering by date
                if self.start_date <= transaction.date_time <= self.end_date:
                    transactions.append(transaction)

            def remove_splits(splited_transactions: List['Transaction']):
                non_split_transactions = []
                # orig_hashes = []
                orig_hashes = {}
                for transaction in splited_transactions:

                    if (transaction.token_address, transaction.transaction_hash) not in orig_hashes.items():
                        non_split_transactions.append(transaction)
                        orig_hashes[transaction.token_address] = transaction.transaction_hash
                    else:
                        for non_split_transaction in non_split_transactions:
                            if (non_split_transaction.transaction_hash, non_split_transaction.token_address) == (transaction.transaction_hash, transaction.token_address):
                                non_split_transaction.value += transaction.value


                    # if transaction._raw_transaction['hash'] not in orig_hashes:
                    #     non_split_transactions.append(transaction)
                    #     orig_hashes.append(transaction._raw_transaction['hash'])
                    # else:
                    #     for i in non_split_transactions:
                    #         if i._raw_transaction['hash'] == transaction._raw_transaction['hash'] and i._raw_transaction['contractAddress'] == transaction._raw_transaction['contractAddress']:
                    #             i.value += transaction.value
                    #         else:  # if diff tokens have same hash
                    #             # tests
                    #             print(transaction.token_symbol)
                    #             continue

                return non_split_transactions

            transactions = remove_splits(transactions)

            print(f'Found {len(transactions)} transactions in range {self.start_date} and {self.end_date}\n')
            return transactions

        # def filter_transactions_by_date_range(transactions: List['Transaction']):
        #     for transaction in transactions

        return etherscan_get_transactions()

    # get wallet tickers (grouped transactions by token symbol)
    def __get_tickers(self) -> List['Ticker']:
        # prepare dict
        grouped_transactions = {}

        for transaction in self.transactions:
            if transaction.token_address in grouped_transactions.keys():
                grouped_transactions[transaction.token_address].append(transaction)
            else:
                grouped_transactions[transaction.token_address] = [transaction]

        # # prepare dict
        # grouped_transactions = {}
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
    def __checking_scam_by_volume_and_liquid_by_data_from_dexguru_for_tickers(self):
        async def get_volume_from_dexguru(tickers: List['Ticker']):
            async def assign_price_for_transaction(async_session, token_address):

                async with async_session.get(
                        url=f'https://api.dev.dex.guru/v1/chain/1/tokens/{token_address}/market',
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
                    # getting volume 24h data
                    if 'volume_24h_usd' not in responses[k].keys():
                        tickers[k].volume_24h_usd = 'N/A'
                        tickers[k].is_valid = False
                    else:
                        tickers[k].volume_24h_usd = float(responses[k]['volume_24h_usd'])
                    # getting liquidity data
                    if 'liquidity_usd' not in responses[k].keys():
                        tickers[k].liquidity_usd = 'N/A'
                        tickers[k].is_valid = False
                    else:
                        tickers[k].liquidity_usd = float(responses[k]['liquidity_usd'])
                    # mark token as scam if it is it
                    if tickers[k].is_valid and (tickers[k].volume_24h_usd < 300 or tickers[k].liquidity_usd < 1000) and tickers[k].total_delta_usd > 0:
                        tickers[k].is_scam = True

                    # if token is scam, and it was trade, we do not balance sum as delta, because user can't sell it
                    # if token is scam, and it was airdrop, we do not collect it for PnL and Winrate metrics

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

    # calculating PNL R and PNL UR
    def __calc_pnl_metrics(self):
        pass

    # calculating Winrate R and Winrate UR


class Transaction:

    def __init__(self, raw_transaction: dict, wallet_address):
        self._raw_transaction = raw_transaction
        self.token_symbol = self._raw_transaction['tokenSymbol']
        self.block_number = self._raw_transaction['blockNumber']
        self.token_address = self._raw_transaction['contractAddress']
        self.transaction_hash = self._raw_transaction['hash']
        self.token_full_name = self._raw_transaction['tokenName']
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
        self.is_valid = True  # if ticker have at least one N/A data - give False valid

        self.volume_24h_usd = 0  # volume for checking scam tokens
        self.liquidity_usd = 0  # liquidity in usd
        self.is_scam = False  # if volume 24 < 300 or liquidity < 1000

        # stablecoin status check
        if self.ticker_symbol in self.stablecoins_list:
            self.is_stablecoin = True
        else:
            self.is_stablecoin = False  # is this token a stablecoin

        # GETTING TOKEN PRICES

        # self.__get_historical_token_prices_from_moralis()
        self.__get_token_prices_from_moralis_by_25_items()
        self.__get_missing_historical_prices_from_dexguru()
        self.__get_actual_token_price_from_moralis()
        self.__get_missing_actual_price_from_dexguru()
        # CALCULATING TOKEN PARAMS
        self.__calc_total_and_tr_amount_params()
        self.__calc_sum_params_and_usd_delta()

    # 1. GETTING TOKEN PRICES #########################################################################################
    #     1.1 getting historical prices from Moralis API
    # get transactions prices from Moralis API by groups of 25 tokens
    def __get_token_prices_from_moralis_by_25_items(self):
        # TODO: try! get prices from moralis by 25 tokens
        # divide transactions by 25 because of API endpoint limit
        parted_transactions = []
        for i in range(0, len(self.transactions), 25):
            parted_transactions.append(
                self.transactions[i:i + 25])  # parted_transactions = [[25 trans], [25 trans], ...]
        # divide transactions by 6 because of Moralis limit
        parted_requests = []
        for i in range(0, len(parted_transactions), 6):  # parted_requests = [[[25], [25], [25], [25], [25], [25]], [..]]
            parted_requests.append(parted_transactions[i:i + 6])
        # make requests by 6 async requests (every requests contains 25 token positions)
        for parted_request in parted_requests:
            asyncio.run(self.__async_get_25_hist_prices_from_moralis(six_requests=parted_request))

    async def __async_get_25_hist_prices_from_moralis(self, six_requests: List[List['Transaction']]):
        # function for request
        async def get_prices_for_transactions(async_session, tokens: list):
            api_url = 'https://deep-index.moralis.io/api/v2/erc20/prices'

            async with async_session.post(
                    url=api_url,
                    headers={'X-API-Key': self.moralis_api_key},
                    params={'chain': 'eth'},
                    json={'tokens': tokens},
                    timeout=3000
            ) as resp:
                try:
                    response_json = await resp.json()
                except BaseException as e:
                    print(str(e))
                    response_json = {'error': '...'}
                return response_json

        # getting responses
        async with aiohttp.ClientSession() as session:
            tasks = []
            for tokens_group in six_requests:
                # preparing tokens for body
                tokens = []
                for token in tokens_group:
                    tokens.append({
                        'token_address': token.token_address,
                        'to_block': token.block_number
                    })
                # creating event loop
                tasks.append(asyncio.ensure_future(get_prices_for_transactions(
                    async_session=session,
                    tokens=tokens
                )))
            responses = await asyncio.gather(*tasks)
            # assigning prices
            for i in range(len(responses)):
                response_25 = responses[i]
                # tests
                # print(json.dumps(response_25, indent=2))
                for j in range(len(response_25)):
                    if not response_25[j] or 'usdPrice' not in response_25[j].keys() or response_25[j]['usdPrice'] == 'N/A':
                        six_requests[i][j].token_price_usd = 'Moralis can\'t find price'
                    else:
                        six_requests[i][j].token_price_usd = float(response_25[j]['usdPrice'])

    #     1.2 getting missing historical prices for transactions with DexGuru
    def __get_missing_historical_prices_from_dexguru(self):
        # preparing request
        def __get_price_from_dexguru_by_timestamp_range(token_address, begin: int, end: int):
            dexguru_response = requests.get(
                url=f'https://api.dev.dex.guru/v1/chain/1/tokens/{token_address}/market/history',
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
                while True:
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
                        break
                    elif end_ts - begin_ts >= 100000:
                        print(transaction.token_symbol, 'FAIL, could not find data in 100K blocks')
                        transaction.token_price_usd = 'N/A'
                        self.is_valid = False
                        break
                    elif response_json['total'] == 0:
                        begin_ts -= 5000
                        end_ts += 5000
                        # test
                        print(
                            transaction.token_symbol, ': no price data in timestamp range', begin_ts, '-', end_ts)
                        continue

                    transaction.token_price_usd = float(response_json['data'][0]['price_usd'])
                    break

    #     1.3 getting actual price from Moralis API (current_price_usd)
    def __get_actual_token_price_from_moralis(self):
        def get_price_from_moralis(token_address):
            api_url = 'https://deep-index.moralis.io/api/v2/erc20'
            response = requests.get(
                url=api_url + f'/{token_address}/price',
                headers={'X-API-Key': self.moralis_api_key},
                params={
                    'chain': 'eth',
                },
                timeout=3000
            )
            if response.status_code != 200 or 'usdPrice' not in response.json().keys() or response.json()[
                'usdPrice'] == 'NaN':
                return 'Moralis can\'t find price'
            else:
                usd_price = float(response.json()['usdPrice'])
                return usd_price

        self.current_price_usd = get_price_from_moralis(self.token_address)

    #     1.4 getting missing actual price with DexGuru
    def __get_missing_actual_price_from_dexguru(self):
        def get_current_price_from_dexguru(token_address):
            dexguru_response = requests.get(
                url=f'https://api.dev.dex.guru/v1/chain/1/tokens/{token_address}/market',
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
        self.total_delta_usd = self.total_delta * self.current_price_usd
        #       if delta is too small -> down to zero
        if self.total_delta_usd < 1:
            self.total_delta = 0
            self.total_delta_usd = 0
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

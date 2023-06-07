import asyncio
import json

import aiohttp as aiohttp
import requests
import datetime
import time
from typing import List
from etherscan.classes import mixins


class Wallet(mixins.APIKeys):

    def __init__(self, address, start_date, end_date, show_details):
        super().__init__()
        self.wallet_address = address
        self.start_date = start_date
        self.end_date = end_date
        self.show_details = show_details
        self.transactions: List['Transaction'] = self.__get_wallet_transactions()[30:60]
        self.tickers: List['Ticker'] = self.__get_tickers()
        # calculating sum params for tickers after getting scam statuses
        self.__checking_scam_tickers_by_volume_and_liquid_data_from_dexguru()
        for ticker in self.tickers:
            ticker.calc_sum_params_and_usd_delta()
        # sorting
        self.__sorting_tickers_by_sum_delta()
        # metrics
        self.pnl_r_metrics = 0
        self.pnl_ur_metrics = 0
        self.winrate_r = 0
        self.winrate_ur = 0

    # 1. Get wallet transactions from Etherscan API
    def __get_wallet_transactions(self) -> List['Transaction']:
        # PREPARING
        # getting all ERC20 transactions of wallet and removing splits
        def etherscan_get_erc20_transactions() -> list:
            api_url = 'https://api.etherscan.io/api'

            params = {
                'module': 'account',
                'action': 'tokentx',
                'address': self.wallet_address,
                'apikey': self.etherscan_api_key,
                'startblock': 0,
                'endblock': 99999999,
                'sort': 'desc',
            }

            response = requests.get(api_url, params=params).json()
            raw_transactions: list = response['result']
            return raw_transactions

        # getting all Normal transactions of wallet to filter transactions with 'execute' method
        def etherscan_get_normal_transactions_methods() -> dict:
            api_url = 'https://api.etherscan.io/api'

            params = {
                'module': 'account',
                'action': 'txlist',
                'address': self.wallet_address,
                'apikey': self.etherscan_api_key,
                'startblock': 0,
                'endblock': 99999999,
                'sort': 'desc',
            }

            response = requests.get(api_url, params=params).json()
            raw_transactions: list = response['result']

            normal_hashes = {}
            for transaction in raw_transactions:
                normal_hashes[transaction['hash']] = transaction['functionName']

            return normal_hashes  # {hash: function name, hash: function name, ...}

        # removing splits
        def remove_splits(spl_transactions: List['Transaction']):
            non_split_transactions = []
            # orig_hashes = []
            orig_hashes = {}
            for spl_transaction in spl_transactions:

                if (spl_transaction.token_address, spl_transaction.transaction_hash) not in orig_hashes.items():
                    non_split_transactions.append(spl_transaction)
                    orig_hashes[spl_transaction.token_address] = spl_transaction.transaction_hash
                else:
                    for non_split_transaction in non_split_transactions:
                        if (non_split_transaction.transaction_hash, non_split_transaction.token_address) == (spl_transaction.transaction_hash, spl_transaction.token_address):
                            non_split_transaction.value += spl_transaction.value

            return non_split_transactions

        # converting user's date to timestamp for filtering
        def convert_to_timestamp(user_date):  # template of input: d/m/Y (25/05/2023)
            timestamp = int(time.mktime(datetime.datetime.strptime(user_date, '%d/%m/%Y').timetuple()))
            return timestamp

        # IMPLEMENTATION
        # 1.1 Getting data from Etherscan API
        raw_erc20_transactions = etherscan_get_erc20_transactions()
        normal_transactions_dict = etherscan_get_normal_transactions_methods()

        # 1.2 Handling transactions
        splited_transactions = []
        allowed_methods = ['execute', 'swap']
        start_range_ts = convert_to_timestamp(self.start_date)
        end_range_ts = convert_to_timestamp(self.end_date)

        for transaction in raw_erc20_transactions:
            tr_hash = transaction['hash']

            # 1.2.1 Not normal transactions filter (HATEv3 for example)
            if tr_hash not in normal_transactions_dict.keys():
                print(transaction['tokenName'], tr_hash, 'is not normal transaction')
                continue

            # 1.2.2 Not allowed method filter
            elif not [True for method in allowed_methods if method in normal_transactions_dict[tr_hash].lower()]:
                print(transaction['tokenName'], tr_hash, normal_transactions_dict[tr_hash], f'NOT one of {allowed_methods}')
                continue

            # 1.2.3 Stablecoins filter
            if transaction['tokenSymbol'] in self.stablecoins_list:
                continue

            # 1.2.4 Date range filter
            if not (start_range_ts <= int(transaction['timeStamp']) <= end_range_ts):
                continue

            # 1.2.5 Append to final transactions if transaction passed all filters
            splited_transactions.append(Transaction(transaction, self.wallet_address))

        # 1.3 remove splits
        non_splited_transactions = remove_splits(splited_transactions)

        # 1.4 showing amount of transaction that would be used
        print(f'Found {len(non_splited_transactions)} transactions in range {self.start_date} and {self.end_date}\n')
        return non_splited_transactions

    # 2. Get wallet tickers (grouped transactions by token symbol)
    def __get_tickers(self) -> List['Ticker']:
        # 2.1 Prepare dict
        grouped_transactions = {}

        # 2.2 Grouping transactions by contract address: {contract_address: transactions, ...}
        for transaction in self.transactions:
            if transaction.token_address in grouped_transactions.keys():
                grouped_transactions[transaction.token_address].append(transaction)
            else:
                grouped_transactions[transaction.token_address] = [transaction]

        # 2.3 Collecting Ticker objects
        tickers = []
        for token_address, transactions_list in grouped_transactions.items():
            tickers.append(Ticker(token_address, transactions_list))

        # 2.4 reversing to get firstly old operations (for Show Details view)
        tickers.reverse()

        return tickers

    # 3. Getting 24h volume in usd (to check scam)
    def __checking_scam_tickers_by_volume_and_liquid_data_from_dexguru(self):
        # PREPARING
        # Async requests to dexguru for getting volume 24h and liquidity
        async def get_volume_and_liquidity_from_dexguru(tickers: List['Ticker']):
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

        # IMPLEMENTATION
        # 3.1 Requesting data by group of 3 transactions to not overload dexguru
        if len(self.tickers) > 3:
            parts = []
            # grouping by 3 transactions
            start = 0
            end = len(self.tickers)
            step = 3
            for i in range(start, end, step):
                parts.append(self.tickers[i:i + step])

            for part in parts:
                asyncio.run(get_volume_and_liquidity_from_dexguru(part))

        else:
            asyncio.run(get_volume_and_liquidity_from_dexguru(self.tickers))

    # 4. Sorting tickers list by sum_delta_usd param
    def __sorting_tickers_by_sum_delta(self):
        # IMPLEMENTATION
        # 4.1 Handling tickers with invalid data
        for ticker in self.tickers:
            if ticker.sum_delta_usd == 'N/A':
                ticker.sum_delta_usd = -999999999999999.9
        # 4.2 Sorting
        self.tickers.sort(key=lambda x: x.sum_delta_usd, reverse=True)
        # reversing invalid data for tickers
        for ticker in self.tickers:
            if ticker.sum_delta_usd == -999999999999999.9:
                ticker.sum_delta_usd = 'N/A'

        # 4.3 Sorting by total delta value
        zero_delta = []  # if token is fully realised, and wallet doesn't contain this token
        delta_exists = []  # if token is not fully realised, and wallet contains this token
        negative_delta_error = []  # if delta is negative => some tokens were got to wallet not by trade transaction
        n_a = []  # if there is no data on services for this token
        for ticker in self.tickers:
            if not ticker.is_valid:
                n_a.append(ticker)
            elif ticker.total_delta_usd < 0:
                negative_delta_error.append(ticker)
            elif ticker.total_delta_usd == 0:
                zero_delta.append(ticker)
            elif ticker.total_delta_usd > 0:
                delta_exists.append(ticker)
            else:
                n_a.append(ticker)

        # 4.4 Then tickers will be showed in table by groups of zero_d, d_ex, neg_d and n_a tickers
        self.tickers = zero_delta + delta_exists + negative_delta_error + n_a

    # 5. Calculating PNL R and PNL UR
    def __calc_pnl_metrics(self):
        pass


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

    # 1. Handling date data from timestamp (for Show Details view)
    def __get_transaction_date_time(self):
        date_time = datetime.datetime.utcfromtimestamp(int(self._raw_transaction['timeStamp']))
        return str(date_time)

    # 2. Handling value data
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
        self.profit = 0  # profit in %
        self.current_price_usd = 0  # current token price in USD
        self.buy_tr_amount = 0  # a lot of 'buy' transactions
        self.sell_tr_amount = 0  # a lot of 'sell' transactions
        self.is_valid = True  # if ticker have at least one N/A data - give False valid

        self.is_parted = False  # if part of tokens were got from nowhere, but part was sold
        self.fair_part = 0  # part of sell transactions that are equal to amount of buy transactions

        self.volume_24h_usd = 0  # volume for checking scam tokens
        self.liquidity_usd = 0  # liquidity in usd
        self.is_scam = False  # if volume 24 < 300 or liquidity < 1000

        # GETTING TOKEN PRICES
        self.__get_historical_prices_from_moralis_by_25_items()
        self.__get_missing_historical_prices_from_dexguru()
        self.__get_actual_token_price_from_moralis()
        self.__get_missing_actual_price_from_dexguru()
        # CALCULATING TOKEN PARAMS
        self.__calc_total_and_tr_amount_params()

    # 1. GETTING TOKEN PRICES #########################################################################################
    #     1.1 getting historical prices from Moralis API
    # get transactions prices from Moralis API by groups of 25 tokens
    def __get_historical_prices_from_moralis_by_25_items(self):
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
        # PREPARING
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

        # IMPLEMENTATION
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
                for j in range(len(response_25)):
                    if not response_25[j] or 'usdPrice' not in response_25[j].keys() or response_25[j]['usdPrice'] == 'N/A':
                        six_requests[i][j].token_price_usd = 'Moralis can\'t find price'
                    else:
                        six_requests[i][j].token_price_usd = float(response_25[j]['usdPrice'])

    #     1.2 getting missing historical prices for transactions with DexGuru
    def __get_missing_historical_prices_from_dexguru(self):
        # PREPARING
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

        # IMPLEMENTATION
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
                        print(transaction.token_symbol, ': no price data in timestamp range', begin_ts, '-', end_ts)
                        continue

                    transaction.token_price_usd = float(response_json['data'][0]['price_usd'])
                    break

    #     1.3 getting actual price from Moralis API (current_price_usd)
    def __get_actual_token_price_from_moralis(self):
        # PREPARING
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

        # IMPLEMENTATION
        self.current_price_usd = get_price_from_moralis(self.token_address)

    #     1.4 getting missing actual price with DexGuru
    def __get_missing_actual_price_from_dexguru(self):
        # PREPARING
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

        # IMPLEMENTATION
        self.current_price_usd = get_current_price_from_dexguru(self.token_address)

    ###################################################################################################################

    # 2. CALCULATING PARAMS ###########################################################################################
    #     2.1 Calculating total params, transactions amount, profit part, if ticker is parted
    def __calc_total_and_tr_amount_params(self):
        # 2.1.1 Calculating total tokens value and transactions amount with sorting to buy and sell transactions
        for transaction in self.transactions:
            if transaction.type == 'buying':
                self.total_bought += transaction.value
                self.buy_tr_amount += 1
            else:
                self.total_sold += transaction.value
                self.sell_tr_amount += 1

        # 2.1.2 Getting tokens value delta
        self.total_delta = self.total_bought - self.total_sold

        # 2.1.3 Calculating tokens delta in USD
        self.total_delta_usd = self.total_delta * self.current_price_usd
        # * if delta is too small -> down to zero
        if 0 <= abs(self.total_delta_usd) <= 1:
            self.total_delta = 0
            self.total_delta_usd = 0

        # 2.1.4 Calculating part that we will use for calc profit
        # (if 5 get by transfer, 5 get by buying and sell 10 so part is 0.5, that we will take from profit)
        if self.total_delta < 0:
            self.is_parted = True
            if self.total_bought == 0:
                self.fair_part = 0
            else:
                self.fair_part = self.total_bought/self.total_sold

    #     2.2 Calculating total_delta_usd, sum_bought_usd, sum_sold_usd, sum_delta_usd
    #     (! will run after getting scam statuses in Wallet class Init def!)
    def calc_sum_params_and_usd_delta(self):
        # 2.2.1 Sums for every transaction and collecting sum_bought and sum_sold
        for transaction in self.transactions:
            # 2.2.1.1 Calculating sums for every transaction of ticker
            if transaction.token_price_usd != 'N/A':
                transaction.sum_usd = transaction.value * transaction.token_price_usd
            else:
                transaction.sum_usd = 'N/A'

            # 2.2.1.2 Summing for bought and sold operations
            if self.is_valid:
                if transaction.type == 'buying':
                    self.sum_bought_usd += transaction.sum_usd
                else:
                    self.sum_sold_usd += transaction.sum_usd
            else:
                self.sum_bought_usd = 'N/A'
                self.sum_sold_usd = 'N/A'

        # 2.2.2 Sum_delta calc (profit in USD)
        # for usual normal token
        if self.is_valid and not self.is_scam and not self.is_parted:
            self.sum_delta_usd = self.sum_sold_usd - self.sum_bought_usd + self.total_delta_usd
        # if token is scammed, and it was bought by user, we do not add delta to profit
        elif self.is_valid and self.is_scam and not self.is_parted:
            self.sum_delta_usd = self.sum_sold_usd - self.sum_bought_usd
        # for parted tickers in wallet
        elif self.is_valid and self.is_parted:
            self.sum_delta_usd = (self.sum_sold_usd - self.sum_bought_usd)*self.fair_part
        else:
            self.sum_delta_usd = 'N/A'
            # tests
            print(f'{self.ticker_symbol} is not valid')

        # 2.2.3 Profit in % calc
        if self.is_valid and self.sum_delta_usd != 0:
            self.profit = self.sum_delta_usd*100/self.sum_bought_usd
        elif self.is_valid and self.sum_delta_usd == 0:
            self.profit = 0
        else:
            self.profit = 'N/A'

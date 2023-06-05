import json

import requests

bsc_wallet_address = '0x54404f173660269dbbc253943cf83a822efe1ae8'
moralis_api_key = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJub25jZSI6IjljNmYyYTNjLTQ3ZWYtNGUzZi1hMjA1LWI4MGQxOTRmYTUyZCIsIm9yZ0lkIjoiMzM3MjgwIiwidXNlcklkIjoiMzQ2NzYyIiwidHlwZUlkIjoiZDJlY2FhZWUtZTM5Ny00NWI0LWFlMDEtOWU1MjBlMDc5NTFhIiwidHlwZSI6IlBST0pFQ1QiLCJpYXQiOjE2ODUwMTc0ODAsImV4cCI6NDg0MDc3NzQ4MH0.kgyhFF4BeZkBminxaVdYzBv9ZGCtDysvQcZNT-Qul9w'
dexguru_api_key = 's7gGaMVb9u4VoreLjYbVbKT3KrBo8ZGiw7GfSaECpw8'
bscscan_api_key = '4NFV1VDD361VA8KSVSYA6D936XYI7QE5PY'


def bscscan_get_transactions():
    api_url = 'https://api.bscscan.com/api'

    params = {
        'module': 'account',
        'action': 'tokentx',
        'address': bsc_wallet_address,
        'apikey': bscscan_api_key,
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
    return raw_transactions


def get_price_from_moralis(token_address, block_number, timestamp, hash):
    api_url = 'https://deep-index.moralis.io/api/v2/erc20'

    response = requests.get(
        url=api_url + f'/{token_address}/price',
        headers={'X-API-Key': moralis_api_key},
        params={
            'chain': 'bsc',
            'to_block': block_number
        },
        timeout=3000)

    response_json = response.json()

    if 'usdPrice' not in response_json.keys():
        print(f'Moralis can\'t find price at block {block_number}')
        get_price_from_dexguru(token_address, begin=timestamp, end=timestamp, hash=hash)
    else:
        print(f'Price at block {block_number} is {response_json["usdPrice"]}')


def get_price_from_dexguru(token_address, begin, end, hash):

    dexguru_response = requests.get(
        url=f'https://api.dev.dex.guru/v1/chain/56/tokens/{token_address}/market/history',
        headers={
            'api-key': dexguru_api_key
        },
        params={
            'begin_timestamp': begin,
            'end_timestamp': end
        }
    )

    response_json = dexguru_response.json()

    if dexguru_response.status_code != 200:
        print(f'At ts {begin} status code NOT 200')
        return
    elif response_json['total'] == 0:  # TODO: edit for eth
        # test
        print(f'No values at ts {begin}')
        if end-begin <= 100000:
            get_price_from_dexguru(token_address, begin=begin-5000, end=end+5000, hash=hash)
        else:
            print(f'FAIL... Hash: {hash}, token address: {token_address}')
            return
    else:
        print(f'Price at ts {begin + (end - begin)/2}: {response_json["data"][0]["price_usd"]}')
        return


#######################################################################################################################

transactions = bscscan_get_transactions()

for transaction in transactions:
    print(f'{transactions.index(transaction)}/{len(transactions)}')
    print(f'Token symbol: {transaction["tokenSymbol"]}, Token name: {transaction["tokenName"]}')
    try:
        get_price_from_moralis(
            token_address=transaction['contractAddress'],
            block_number=int(transaction['blockNumber']),
            timestamp=int(transaction['timeStamp']),
            hash=transaction['hash']
        )
    except BaseException as e:
        print(str(e))
    print('\n')


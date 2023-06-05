from datetime import date

import requests
from web3 import Web3


sParty1 = {
        "transactions": [
            {
                "blockNumber": "17057608",
                "timeStamp": "1681625471",
                "hash": "0xaddf43e35d1e627e7d75ccddf19ff13fd44aed762ea06c7f55d26b0c2c09f1a5",
                "contractAddress": "0xc01dcef6c78a4978f3411d518be9f36f2be1444f",
                "value": 842.35,
                "tokenName": "Pool Party 1",
                "tokenSymbol": "sPARTY1",
                "type": "selling",
                "raw_value": 842350000000000000000,
                "date_time": "2023-04-16 06:11:11",
                "time_since": "40 days, 2:58:40.327359",
                "token_price_usd": "N/A",
                "sum_usd": "N/A"
            },
            {
                "blockNumber": "17008010",
                "timeStamp": "1681009811",
                "hash": "0x00de14ef6577ee1dd0f0ebaae2eb4d7128e59ce67e6154ff573959e512ff3fe9",
                "contractAddress": "0xc01dcef6c78a4978f3411d518be9f36f2be1444f",
                "value": 990.0,
                "tokenName": "Pool Party 1",
                "tokenSymbol": "sPARTY1",
                "type": "buying",
                "raw_value": 990000000000000000000,
                "date_time": "2023-04-09 03:10:11",
                "time_since": "47 days, 5:59:40.333759",
                "token_price_usd": "N/A",
                "sum_usd": "N/A"
            }
        ],
        "total_bought": 990.0,
        "total_sold": 842.35,
        "total_delta": 147.64999999999998,
        "total_delta_usd": "N/A",
        "sum_bought_usd": "N/A",
        "sum_sold_usd": "N/A",
        "sum_delta_usd": "N/A",
        "current_price_usd": "N/A",
        "buying_amount": 1,
        "selling_amount": 1
    }

timestamp = sParty1['transactions'][0]['timeStamp']
token_address = sParty1['transactions'][0]['contractAddress']



# Подключаемся к сети Ethereum
w3 = Web3(Web3.HTTPProvider('https://mainnet.infura.io/v3/34ba9ec60ffd4895ac67e6ef7803641c'))

# Задаем адрес токена
# token_address = '0x1234567890123456789012345678901234567890'

# Задаем дату или timestamp
#date = '2022-01-01'
#timestamp = 1640995200

# Получаем цену токена на указанную дату или timestamp
# if date:
#     timestamp = int(datetime.strptime(date, '%Y-%m-%d').timestamp())
# price = w3.eth.getStorageAt(token_address, timestamp)
price = w3.eth.get_storage_at(token_address, timestamp)
print(price)

# Задаем курс ETH/USD на момент транзакции
# timestamp = int(transactions[0]['timeStamp'])
url = f'https://api.coingecko.com/api/v3/coins/ethereum/history?date={timestamp}&localization=false'
response = requests.get(url)
eth_usd_price = response.json()['market_data']['current_price']['usd']

# Рассчитываем стоимость каждой транзакции в долларах
# for tx in transactions:
value = sParty1['transactions'][0]['value']

eth_amount = value
eth_price = float(w3.eth.get_storage_at(token_address, timestamp))
tx_cost_usd = eth_amount * eth_price * eth_usd_price
print(f'Transaction of sParty1 cost {tx_cost_usd:.2f} USD')
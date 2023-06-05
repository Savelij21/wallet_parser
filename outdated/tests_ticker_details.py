import json
from outdated import parsers

eth_wallet_address = '0x42b27c044a22acaff04146aa243753ee617a59b5'
etherscan_api_key = 'Q783CC2MQ1C5QH2IJB4YWPEE4EIJRGFMR5'

bsc_wallet_address = '0x54404f173660269dbbc253943cf83a822efe1ae8'
bscscan_api_key = '4NFV1VDD361VA8KSVSYA6D936XYI7QE5PY'

transactions = parsers.etherscan_get_transactions(
    wallet_address=eth_wallet_address,
    api_key=etherscan_api_key
)

transactions = parsers.edit_transaction_fields(transactions, eth_wallet_address)
grouped_transactions = parsers.grouping_transactions_by_ticker(transactions)


print(json.dumps(grouped_transactions['WETH'], indent=2))


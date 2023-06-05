import json

import openpyxl
from outdated import parsers
from outdated.moralis import moralis
from outdated.excel_tools import create_excel

eth_wallet_address = '0x42b27c044a22acaff04146aa243753ee617a59b5'
etherscan_api_key = 'Q783CC2MQ1C5QH2IJB4YWPEE4EIJRGFMR5'

bsc_wallet_address = '0x54404f173660269dbbc253943cf83a822efe1ae8'
bscscan_api_key = '4NFV1VDD361VA8KSVSYA6D936XYI7QE5PY'

# coinapi_key = '2E553B29-A7E2-4090-B69B-5784A87E4707'
# cryptocompare_api_key = 'cca3e8d22a04de24c51ab20644855145cdf348ad77b6211b9edf851b42964f8b'
# coinmarket_api_key = '8b1bc6e0-da21-41ad-a487-19d7f14643d4'
dex_guru_api_key = 's7gGaMVb9u4VoreLjYbVbKT3KrBo8ZGiw7GfSaECpw8'
moralis_x_api_key = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJub25jZSI6ImM3MDM4Yjk4LTI2MGQtNDI3Yy1hMTQwLWE5Nzk3ZjdiOThjYSIsIm9yZ0lkIjoiMzM2NjYzIiwidXNlcklkIjoiMzQ2MTMwIiwidHlwZUlkIjoiZGUyYmQ1NDMtZjFkNS00N2VhLWJmOTAtOTI1NWFhNDY3YzFhIiwidHlwZSI6IlBST0pFQ1QiLCJpYXQiOjE2ODQ4NjczMzAsImV4cCI6NDg0MDYyNzMzMH0.Z2G0YkBHZuIADEf_dSBKyy2T2A99SeE_fD9rwbPNZI8'

# get transactions, editing fields and grouping by ticker
transactions = parsers.etherscan_get_transactions(
    wallet_address=eth_wallet_address,
    api_key=etherscan_api_key
)
edited_transactions = parsers.edit_transaction_fields(transactions,
                                                      wallet_address=eth_wallet_address)  # [1000:1010]  # test
transactions_with_price = moralis.transactions_prices(transactions=edited_transactions)
tickers = parsers.grouping_transactions_by_ticker(transactions_with_price)
##################################################


# TODO: GETTING JSON WITH TICKERS FROM MORALIS API
failed_tickers = []
for ticker in tickers.keys():
    try:
        moralis.get_ticker_price_and_sum_metrics(tickers[ticker])
    except BaseException as e:
        failed_tickers.append({'ticker': ticker, 'exception': str(e)})
        continue

# Serializing json
json_object = json.dumps(tickers, indent=4)



# Writing to sample.json
# with open("moralis.json", "w") as outfile:
#     outfile.write(json_object)
#
# json_failed = json.dumps({'failed_tickers': failed_tickers}, indent=4)
# with open("failed_tickers.json", "w") as outfile:
#     outfile.write(json_failed)


with open('../etherscan/full_parsed_data/moralis.json') as f:
    tickers = json.load(f)

# excel
book = openpyxl.Workbook()
sheet = book['Sheet']
sheet['B1'] = eth_wallet_address
create_excel.create_template(sheet)

current_string = 5
# for ticker in tickers.keys():
for ticker in tickers:
    try:
        create_excel.ticker_block(
            ticker=tickers[ticker],
            current_string=current_string,
            sheet=sheet
        )
    except BaseException:
        current_string += len(tickers[ticker]['transactions']) + 1
        continue

    current_string += len(tickers[ticker]['transactions']) + 1

for i in range(5, 3628):
    if sheet[f'E{i}'].value is None:
        continue
    elif sheet[f'E{i}'].value < 0:
        print(f'str {i}, delta {sheet[f"E{i}"].value}, ticker {sheet[f"A{i}"].value}')

book.save('test1.xlsx')

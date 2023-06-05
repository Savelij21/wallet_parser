import openpyxl, json
from outdated.excel_tools import create_excel

eth_wallet_address = '0x42b27c044a22acaff04146aa243753ee617a59b5'

with open('moralis.json') as f:
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

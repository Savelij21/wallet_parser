import time
from etherscan.classes import excel_classes_v2, wallet_classes_v2

# TODO:
#           1. решить, какие методы будем допускать для добавления транзакции в таблицу
#           2. посчитать метрики кошелька - !!!!!


# INPUT data:
network = 'eth'  # network for scanning
eth_wallet_address = '0x42b27c044a22acaff04146aa243753ee617a59b5' # '0x5c33fafCF6317C71B2BE4291506EA5c3aC099aAD'  wallet for parsing
start_date = '01/01/2003'  # dd/mm/yyyy: start point for diapason
end_date = '01/10/2033'  # dd/mm/yyyy: end point for diapason
show_details_ticker = 'No'  # show all transactions of ticker in Excel (Да/Нет)

# convert show_details
if show_details_ticker == 'Yes':
    show_details_ticker = True
else:
    show_details_ticker = False

# script
start = time.time()  # test speed of work
print(time.strftime("%H:%M:%S", time.localtime()), 'parsing started\n')

# wallet initiating (scanning, parsing)
eth_wallet = wallet_classes_v2.Wallet(
    address=eth_wallet_address,
    start_date=start_date,
    end_date=end_date,
    show_details=show_details_ticker
)

end = time.time()  # test speed
print(end - start, 'for parsing process')  # test speed


# excel creating
excel_file = excel_classes_v2.ExcelWallet(eth_wallet)
excel_file.save(f'test_excel_files/{eth_wallet_address}_details_{show_details_ticker}.xlsx')


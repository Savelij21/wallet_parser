import time
from bscscan.classes import excel_classes, wallet_classes

# TODO:
#           3.посчитать метрики кошелька - !!!!!

# INPUT data:
network = 'bsc'  # network for scanning
bsc_wallet_address = '0x54404f173660269dbbc253943cf83a822efe1ae8'
start_date = '2003-01-01 00:00:00'  # YYYY-MM-DD: start point for diapason
end_date = '2033-04-11 00:00:00'  # YYYY-MM-DD: end point for diapason
# in development
show_details_ticker = 'Yes'  # show all transactions of ticker in Excel (Да/Нет)
if show_details_ticker == 'Yes':
    show_details_ticker = True
else:
    show_details_ticker = False

# script
start = time.time()  # test speed of work

# wallet initiating (scanning, parsing)
eth_wallet = wallet_classes.Wallet(
    address=bsc_wallet_address,
    start_date=start_date,
    end_date=end_date,
    show_details=show_details_ticker
)

end = time.time()  # test speed
print(end - start, 'for parsing process')  # test speed


# excel creating
excel_file = excel_classes.ExcelWallet(eth_wallet)
excel_file.save(f'{bsc_wallet_address}_details_{show_details_ticker}.xlsx')


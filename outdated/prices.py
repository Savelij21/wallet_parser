


my_list = [1, 2, 3, 4, 5,
           6, 7, 8, 9, 10]
start = 0
end = len(my_list)
step = 3
for i in range(start, end, step):
    x = i
    print(my_list[x:x+step])
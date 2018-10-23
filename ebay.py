import config
import csv
import requests

baseurl = 'https://svcs.ebay.com/services/search/FindingService/v1'

baseparams = {
	'OPERATION-NAME' : 'findItemsIneBayStores',
	'SERVICE-VERSION' : '1.0.0',
	'SECURITY-APPNAME' : config.key,
	'RESPONSE-DATA-FORMAT' : 'JSON',
	'REST-PAYLOAD' : '',
	'storeName' : 'Suspension Specialists'
	}
	
r = requests.get(baseurl, params=baseparams)

if (r.status_code != 200):
	print("FAILURE")
	print("ERROR " + str(r.status_code))
	print("EXITING")
	exit()

final_dict = {}
	
obj = r.json()

pageInfo = obj['findItemsIneBayStoresResponse'][0]['paginationOutput'][0]
totalPages = pageInfo['totalPages'][0]

searchResults = obj['findItemsIneBayStoresResponse'][0]['searchResult'][0]

for eachItem in searchResults['item']:
	itemId = eachItem['itemId'][0]
	final_dict[itemId] = {}
	final_dict[itemId]['price']	= eachItem['sellingStatus'][0]['currentPrice'][0]['__value__']
	
with open('out.csv', 'w', newline='') as outfile:
	writer = csv.writer(outfile)
	writer.writerow(['SKU','PRICE'])
	for eachItem in final_dict:
		writer.writerow([eachItem, final_dict[eachItem]['price']])
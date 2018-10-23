import config
import csv
import datetime
import requests

baseurl = 'https://svcs.ebay.com/services/search/FindingService/v1'

currentPage = 1
totalPages = 1

final_dict = {}

print("Enter Store Name => ")
storeName = input()
print("Working...")

baseparams = {
	'OPERATION-NAME' : 'findItemsIneBayStores',
	'SERVICE-VERSION' : '1.0.0',
	'SECURITY-APPNAME' : config.key,
	'RESPONSE-DATA-FORMAT' : 'JSON',
	'REST-PAYLOAD' : '',
	'storeName' : storeName,
	'paginationInput.pageNumber' : '1'
	}
	

def writeOutAndClose():	
	timestamp = datetime.datetime.now().strftime("%Y-%m-%d-%I%M%S%p--%f")
	
	with open(storeName + "--" + timestamp + ".csv", 'w', newline='') as outfile:
		writer = csv.writer(outfile)
		writer.writerow(['SKU','PRICE'])
		for eachItem in final_dict:
			writer.writerow([eachItem, final_dict[eachItem]['price']])
	exit()

	
while (currentPage <= totalPages):
	currentParams = baseparams
	currentParams['paginationInput.pageNumber'] = currentPage
	
	r = requests.get(baseurl, params=currentParams)

	if (r.status_code != 200):
		print("ERROR! " + str(r.status_code))
		print("Dumping what I have end exiting.")
		writeOutAndClose()
		
	obj = r.json()
	
	totalPages = int(obj['findItemsIneBayStoresResponse'][0]['paginationOutput'][0]['totalPages'][0])
		
	searchResults = obj['findItemsIneBayStoresResponse'][0]['searchResult'][0]
	
	for eachItem in searchResults['item']:
		itemId = eachItem['itemId'][0]
		final_dict[itemId] = {}
		final_dict[itemId]['price'] = eachItem['sellingStatus'][0]['currentPrice'][0]['__value__']
	
	currentPage = currentPage + 1
	
writeOutAndClose()
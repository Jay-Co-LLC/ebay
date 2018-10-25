import config
import sys
import os
import csv
import datetime
import requests

def mkdirIfNotExists(path):
	if (not os.path.isdir(path)):
		os.mkdir(path)

def writeOutAndClose():	
	timestamp = datetime.datetime.now().strftime("%Y-%m-%d-%I%M%S%p--%f")
	filename = storeName + "--" + timestamp + ".csv"
	
	mkdirIfNotExists(storeName)
	
	# write out the filename of this run to use for comparing to next run
	with open(storeName + '/' + storeName, 'w') as outfile:
		outfile.write(filename)
	
	# write out the data
	with open(storeName + '/DATA__' + filename, 'w', newline='') as outfile:
		writer = csv.writer(outfile)
		for eachItem in current:
			writer.writerow([eachItem['itemId'], eachItem['price']])
				
	# write out the report
	if (previousData != {}):
		with open(storeName + '/REPORT__' + filename, 'w', newline='') as reportfile:
			writer = csv.DictWriter(reportfile, fieldnames=['itemId','price','last_price','price_difference','status'])
			writer.writeheader()
			for eachItem in current:
				if (eachItem['status'] != 'NOCHANGE'):
					writer.writerow(eachItem)
		
	exit()

if (not len(sys.argv) == 2):
	print("Usage: python ebay.py [storeName]")
	exit()	
	
storeName = sys.argv[1]
	
baseurl = 'https://svcs.ebay.com/services/search/FindingService/v1'
	
baseparams = {
	'OPERATION-NAME' : 'findItemsIneBayStores',
	'SERVICE-VERSION' : '1.0.0',
	'SECURITY-APPNAME' : config.key,
	'RESPONSE-DATA-FORMAT' : 'JSON',
	'REST-PAYLOAD' : '',
	'storeName' : storeName,
	'paginationInput.pageNumber' : '1'
	}

currentPage = 1
totalPages = 1

previousFilename = ''
previousData = {}

current = []
	
# check for previous run file, load previous data into memory
if (os.path.exists(storeName + '/' + storeName)):
	with open(storeName + '/' + storeName) as previousRunFile:
		previousDataFilename = previousRunFile.read()
		
	with open(storeName + '/DATA__' + previousDataFilename) as previousDataFile:
		previousData = dict(csv.reader(previousDataFile))
			
while (currentPage <= totalPages):
	currentParams = baseparams
	currentParams['paginationInput.pageNumber'] = currentPage
	
	r = requests.get(baseurl, params=currentParams)

	if (r.status_code != 200):
		print("ERROR! " + str(r.status_code))
		print("Dumping what I have and exiting.")
		writeOutAndClose()
		
	obj = r.json()
	
	if (obj['findItemsIneBayStoresResponse'][0]['ack'][0] == "Failure"):
		print("ERROR: " + obj['findItemsIneBayStoresResponse'][0]['errorMessage'][0]['error'][0]['message'][0])
		print("Dumping what I have and exiting.")
		writeOutAndClose()
		
	totalPages = int(obj['findItemsIneBayStoresResponse'][0]['paginationOutput'][0]['totalPages'][0])	
	searchResults = obj['findItemsIneBayStoresResponse'][0]['searchResult'][0]
	
	for eachItem in searchResults['item']:
		itemId = eachItem['itemId'][0]
		
		current_item = {
			'itemId' : itemId,
			'price' : eachItem['sellingStatus'][0]['currentPrice'][0]['__value__']
		}
				
		# if no previous run, don't worry about reporting stuff
		if (previousData == {}):
			current.append(current_item)
			continue
			
		# If not in previous data, mark as new item
		if (itemId not in previousData):
			current_item['last_price'] = 'N/A'
			current_item['price_difference'] = 'N/A'
			current_item['status'] = 'NEW'
		else:
			current_item['last_price'] = previousData[itemId]
			difference = float(current_item['price']) - float(current_item['last_price'])
			current_item['price_difference'] = difference
			
			if (difference < 0):
				current_item['status'] = 'REDUCED'
			elif (difference > 0):
				current_item['status'] = 'INCREASED'
			else:
				current_item['status'] = 'NOCHANGE'
		
		current.append(current_item)
	
	currentPage = currentPage + 1
	
writeOutAndClose()
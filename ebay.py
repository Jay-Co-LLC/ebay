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
	
	mkdirIfNotExists('data/' + storeName)
	
	with open('data/' + storeName + "/" + filename, 'w', newline='') as outfile:
		writer = csv.writer(outfile)
		writer.writerow(['SKU','PRICE'])
		for eachItem in current_data_dict:
			writer.writerow([eachItem, current_data_dict[eachItem]['price']])
		
	# write out the filename of this run to use for comparing to next run
	with open('data/' + storeName + '/' + storeName, 'w') as outfile:
		outfile.write(filename)
		
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

paths = {
	'storeData' : 'data/' + storeName,
	'storePreviousRunFile' : 'data/' + storeName + '/' + storeName
	}

currentPage = 1
totalPages = 1

previousDataFilename = ''
previousData = {}

current_data_dict = {}
current_dupes_dict = {}
	
mkdirIfNotExists('data')
mkdirIfNotExists('reports')

# check for previous run file, load previous data into memory
if (os.path.exists(paths['storePreviousRunFile'])):
	with open(paths['storePreviousRunFile']) as previousRunFile:
		previousDataFilename = previousRunFile.read()
		
	with open(paths['storeData'] + "/" + previousDataFilename) as previousDataFile:
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
		
		if (itemId in current_data_dict):
			print("DUPLICATE FOUND: " + str(itemId))
			continue
			
		current_data_dict[itemId] = {}
		current_data_dict[itemId]['price'] = eachItem['sellingStatus'][0]['currentPrice'][0]['__value__']
	
	currentPage = currentPage + 1
	
writeOutAndClose()
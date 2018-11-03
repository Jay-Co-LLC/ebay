import sys
import os
import csv
import datetime
import boto3
import logging
import requests

s3 = boto3.resource('s3')
bucket = s3.Bucket('ebayreports')

logger = logging.getLogger()

storeName = os.environ['storeName']
apiKey = os.environ['apiKey']

baseurl = 'https://svcs.ebay.com/services/search/FindingService/v1'
	
baseparams = {
	'OPERATION-NAME' : 'findItemsIneBayStores',
	'SERVICE-VERSION' : '1.0.0',
	'SECURITY-APPNAME' : apiKey,
	'RESPONSE-DATA-FORMAT' : 'JSON',
	'REST-PAYLOAD' : '',
	'storeName' : storeName,
	'paginationInput.pageNumber' : '1'
	}

previousFilename = ''
previousData = {}
previousTimestamp = ''

currentData = {}
currentReport = []

def writeOutAndClose():	
	timestamp = datetime.datetime.now().strftime("%Y%m%d%I%M%S%p%f")
	filename = timestamp + '.csv'
	
	# write out the timestamp of this run
	with open('/tmp/LASTRUN', 'w', newline='') as timefile:
		timefile.write(timestamp)
	
	# write out the data
	with open('/tmp/DATA__' + filename, 'w', newline='') as outfile:
		writer = csv.writer(outfile)
		for itemid in currentData:
			writer.writerow([itemid, currentData[itemid]])
				
	# write out the report
	if (currentReport != []):
		with open('/tmp/REPORT__' + filename, 'w', newline='') as reportfile:
			writer = csv.DictWriter(reportfile, fieldnames=['itemId','price','last_price','price_difference','status','url','list_date'])
			writer.writeheader()
			for eachItem in currentReport:
				writer.writerow(eachItem)
		
		s3.Object('ebayreports', storeName + '/REPORT__' + filename).put(Body=open('/tmp/REPORT__' + filename, 'rb'))
		
	s3.Object('ebayreports', storeName + '/LASTRUN').put(Body=open('/tmp/LASTRUN', 'rb'))	
	s3.Object('ebayreports', storeName + '/DATA').put(Body=open('/tmp/DATA__' + filename, 'rb'))
	
def getLastRunTime():
	try:
		return datetime.datetime.strptime(bucket.Object(storeName + '/LASTRUN').get()['Body'].read().decode('utf-8'), '%Y%m%d%I%M%S%p%f')
	except:
		logger.error("LASTRUN file does not exist or is corrupt")
		return ''
		
def getLastRunData():
	try:
		previousDataFileObj = bucket.Object(storeName + '/DATA')
		res = previousDataFileObj.get()
		ret = dict([each.split(',') for each in res['Body'].read().decode('utf-8').split()])
		previousDataFileObj.delete()
		return ret
	except:
		logger.error("DATA file does not exist or is corrupt")
		return {}
		

def main(event, context):
	
	# Get timestamp of last run
	previousTimeObj = getLastRunTime()
	
	# Load previous data file into memory if it exists
	previousData = getLastRunData()
	
	currentPage = 1
	totalPages = 1
		
	while (currentPage <= totalPages):
		currentParams = baseparams
		currentParams['paginationInput.pageNumber'] = currentPage
		
		r = requests.get(baseurl, params=currentParams)
		
		if (r.status_code != 200):
			logger.error("Unable to complete eBay API request " + str(currentPage) + "/" + str(totalPages) + ": " + str(r.status_code))
			logger.error("Dumping what I have and exiting...")
			writeOutAndClose()
			raise Exception("eBay API GET Request Failed:  " + r.status_code)
	
		obj = r.json()
		
		if (obj['findItemsIneBayStoresResponse'][0]['ack'][0] == "Failure"):
			logger.error("eBay API ACK Failure: " + obj['findItemsIneBayStoresResponse'][0]['errorMessage'][0]['error'][0]['message'][0])
			logger.error("Dumping what I have and exiting.")
			writeOutAndClose()
			raise Exception("eBay API ACK FAILURE")
			
		totalPages = int(obj['findItemsIneBayStoresResponse'][0]['paginationOutput'][0]['totalPages'][0])	
		searchResults = obj['findItemsIneBayStoresResponse'][0]['searchResult'][0]
		
		# loop through each item in the current page of results, add it to data, add it to report if needed
		for eachItem in searchResults['item']:
			itemId = eachItem['itemId'][0]
			price = eachItem['sellingStatus'][0]['currentPrice'][0]['__value__']
			
			currentItem = {
				'itemId' : itemId,
				'price' : price
			}
					
			# add the current item to the current data set no matter what
			currentData[itemId] = price
				
			# If item in previous data set, add it to the report if there's been a change
			if (itemId in previousData):
				price_difference = float(currentItem['price']) - float(previousData[itemId])
				
				# If there's been no change in the price, don't add it to the report
				if (price_difference == 0): 
					continue
						
				currentItem['last_price'] = previousData[itemId]
				currentItem['price_difference'] = price_difference
				
				if (price_difference < 0):
					currentItem['status'] = 'REDUCED'
				elif (price_difference > 0):
					currentItem['status'] = 'INCREASED'
					
				currentItem['list_date'] = eachItem['listingInfo'][0]['startTime'][0]
					
				currentReport.append(currentItem)
			else:
				# if item id not in previous data, check timestamps to see if it's actually new
				currentListTime = datetime.datetime.strptime(eachItem['listingInfo'][0]['startTime'][0],'%Y-%m-%dT%H:%M:%S.000Z')

				if (previousTimestamp and previousTimeObj <= currentListTime):
					currentItem['status'] = 'NEW'
					currentItem['last_price'] = ''
					currentItem['price_difference'] = ''
					currentItem['list_date'] = eachItem['listingInfo'][0]['startTime'][0]
				
					currentReport.append(currentItem)
				
		
		currentPage = currentPage + 1
	
	# Once we've gotten through all the listings, use set operations to find new and removed listings
	if previousData:
		currentSkus = set([itemid for itemid in currentData])
		previousSkus = set([itemid for itemid in previousData])

		removedItems = previousSkus - currentSkus

		if removedItems:
			for itemid in removedItems:
				# Call the eBay API for each itemid to see if it returns a listing, to eliminate false positives
				currentParams = {
					'OPERATION-NAME' : 'findItemsByKeyword',
					'SERVICE-VERSION' : '1.0.0',
					'SECURITY-APPNAME' : apiKey,
					'RESPONSE-DATA-FORMAT' : 'JSON',
					'REST-PAYLOAD' : ''
					}
					
				currentParams['keywords'] = str(itemid)	
		
				r = requests.get(baseurl, params=currentParams)
				
				obj = r.json()
				
				print(obj)
				
				# if the count returned is not 0, this itemid is an active listing so it wasn't removed
				if (obj[0]['searchResult'][0]['@count'] > 0):
					continue
				
				toAdd = {
					'itemId' : itemid,
					'price' : '',
					'last_price' : previousData[itemid],
					'price_difference' : '',
					'status' : 'REMOVED'
					}
				currentReport.append(toAdd)
				
	writeOutAndClose()
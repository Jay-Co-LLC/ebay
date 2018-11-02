import sys
import os
import csv
import datetime
import boto3
import logging
import requests

def main(event, context):

	def writeOutAndClose():	
		timestamp = datetime.datetime.now().strftime("%Y%m%d%I%M%S%p%f")
		filename = timestamp + '.csv'
		
		# write out the filename of this run to use for comparing to next run
		with open('/tmp/' + storeName, 'w') as outfile:
			outfile.write(filename)
		
		# write out the data
		with open('/tmp/DATA__' + filename, 'w', newline='') as outfile:
			writer = csv.writer(outfile)
			for itemid in currentData:
				writer.writerow([itemid, currentData[itemid]])
					
		# write out the report
		if (currentReport != []):
			with open('/tmp/REPORT__' + filename, 'w', newline='') as reportfile:
				writer = csv.DictWriter(reportfile, fieldnames=['itemId','price','last_price','price_difference','status','url'])
				writer.writeheader()
				for eachItem in currentReport:
					if (eachItem['status'] != 'NOCHANGE'):
						writer.writerow(eachItem)
			
			s3.Object('ebayreports', storeName + '/REPORT__' + filename).put(Body=open('/tmp/REPORT__' + filename, 'rb'))
			
		s3.Object('ebayreports', storeName + '/DATA__' + filename).put(Body=open('/tmp/DATA__' + filename, 'rb'))
		s3.Object('ebayreports', storeName + '/' + storeName).put(Body=open('/tmp/' + storeName, 'rb'))
	
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
	
	currentData = {}
	currentReport = []
	
	currentPage = 1
	totalPages = 1
	
	# check for previous run file, load previous data into memory
	try:
		response = bucket.Object(storeName + '/' + storeName).get()
		previousFilename = response['Body'].read().decode('utf-8')
	except:
		logger.info("No previous run file detected.")
	
	if (previousFilename):
		try:
			filetograb = storeName + '/DATA__' + previousFilename
			response2 = bucket.Object(filetograb).get()
		except:
			logger.error("Could not find previous data file")
		
		try:
			previousData = dict([each.split(',') for each in response2['Body'].read().decode('utf-8').split()])
		except:
			logger.error("Unable to parse previous data file")
		
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
			raise Exception("eBay API ACK FAILURE: " + obj['findItemsIneBayStoresResponse'][0]['errorMessage'][0]['error'][0]['message'][0]")
			
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
					
				currentReport.append(currentItem)
		
		currentPage = currentPage + 1
	
	# Once we've gotten through all the listings, use set operations to find new and removed listings
	if False:
		if previousData:
			currentSkus = set([itemid for itemid in currentData])
			previousSkus = set([itemid for itemid in previousData])
	
			newItems = currentSkus - previousSkus
			removedItems = previousSkus - currentSkus
	
			if newItems:
				for itemid in newItems:
					toAdd = {
						'itemId' : itemid,
						'price' : currentData[itemid],
						'last_price' : '',
						'price_difference' : '',
						'status' : 'NEW'
						}
					currentReport.append(toAdd)
					
			if removedItems:
				for itemid in removedItems:
					toAdd = {
						'itemId' : itemid,
						'price' : '',
						'last_price' : previousData[itemid],
						'price_difference' : '',
						'status' : 'REMOVED'
						}
					currentReport.append(toAdd)
				
	writeOutAndClose()
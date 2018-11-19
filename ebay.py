import sys
import os
import csv
import datetime
import openpyxl as XL
import boto3
import logging
import requests

bucket = boto3.resource('s3').Bucket('ebayreports')

logger = logging.getLogger()
logger.setLevel(logging.ERROR)

storeNames = os.environ['storeNames'].split(',')
apiKey = os.environ['apiKey']

baseurl = 'https://svcs.ebay.com/services/search/FindingService/v1'
	
baseparams = {
	'OPERATION-NAME' : 'findItemsIneBayStores',
	'SERVICE-VERSION' : '1.0.0',
	'SECURITY-APPNAME' : apiKey,
	'RESPONSE-DATA-FORMAT' : 'JSON',
	'REST-PAYLOAD' : '',
	'storeName' : storeNames[0],
	'paginationInput.pageNumber' : '1'
	}
	
report_fields = [
	'itemid',
	'status',
	'title',
	'price',
	'last_price',
	'price_difference',
	'url'
	]
	
currentDate = datetime.datetime.now() - datetime.timedelta(hours=8)

def writeOutAndClose(storeName, currentData, currentReport):	

	# write out the timestamp of this run
	logger.info(f"[{storeName}] Writing LASTRUN...")
	with open("/tmp/LASTRUN", 'w', newline='') as timeFile:
		timeFile.write(f"{currentDate}")
	
	# write out the data
	logger.info(f"[{storeName}] Writing DATA...")
	with open(f"/tmp/DATA", 'w', newline='') as dataFile:
		writer = csv.writer(dataFile)
		for itemid in currentData:
			writer.writerow([itemid, currentData[itemid]])
				
	# write out the report
	if currentReport:
		logger.info(f"[{storeName}] Writing REPORT...")
		wb = XL.Workbook()
		ws = wb.active
		ws.append(report_fields)
		
		for eachItem in currentReport:
			ws.append([eachItem[field] for field in report_fields])
			
		wb.save("/tmp/REPORT.xlsx")
		
		bucket.Object(f"{storeName}/REPORT - {storeName} - {currentDate.strftime('%m-%d-%Y %I:%M%p')}.xlsx").put(Body=open("/tmp/REPORT.xlsx", 'rb'))

	bucket.Object(f"{storeName}/LASTRUN").put(Body=open("/tmp/LASTRUN", 'rb'))	
	bucket.Object(f"{storeName}/DATA").put(Body=open(f"/tmp/DATA", 'rb'))
	
def getLastRunTime(storeName):
	try:
		timestring = bucket.Object(f"{storeName}/LASTRUN").get()['Body'].read().decode('utf-8')
		return datetime.datetime.strptime(timestring, '%Y-%m-%d %H:%M:%S.%f')
	except Exception as err:
		logger.info(f"[{storeName}] Error reading LASTRUN: {err}")
		return ''
		
def getLastRunData(storeName):
	try:
		previousDataFileObj = bucket.Object(f"{storeName}/DATA")
		res = previousDataFileObj.get()
		ret = dict([each.split(',') for each in res['Body'].read().decode('utf-8').split()])
		previousDataFileObj.delete()
		return ret
	except Exception as err:
		logger.error(f"[{storeName}] Error reading DATA: {err}")
		return {}
		
def main(event, context):
	
	for storeName in storeNames:
		previousFilename = ''
		previousData = {}
		previousTimestamp = ''

		currentData = {}
		currentReport = []
	
		# Get timestamp of last run
		previousTimeObj = getLastRunTime(storeName)
		
		# Load previous data file into memory if it exists
		previousData = getLastRunData(storeName)
		
		currentPage = 1
		totalPages = 1
		
		logger.info(f"[{storeName}] Starting...")
			
		while (currentPage <= totalPages):
			currentParams = baseparams
			currentParams['storeName'] = storeName
			currentParams['paginationInput.pageNumber'] = currentPage
			
			logger.info(f"[{storeName}] Reading page {currentPage}/{totalPages}")
			
			r = requests.get(baseurl, params=currentParams)
			
			# if error retrieving data from eBay, move to next seller
			# to avoid overwriting data file with partial data
			if (r.status_code != 200):
				logger.error(f"[{storeName}] HTTP response {r.status_code}")
				break
		
			obj = r.json()
			
			if (obj['findItemsIneBayStoresResponse'][0]['ack'][0] == "Failure"):
				logger.error(f"[{storeName}] ACK FAILURE: {obj['findItemsIneBayStoresResponse'][0]['errorMessage'][0]['error'][0]['message'][0]}")
				break
				
			totalPages = int(obj['findItemsIneBayStoresResponse'][0]['paginationOutput'][0]['totalPages'][0])	
			searchResults = obj['findItemsIneBayStoresResponse'][0]['searchResult'][0]
			
			# loop through each item in the current page of results, add it to data, add it to report if needed
			for eachItem in searchResults['item']:
				itemId = eachItem['itemId'][0]
				price = eachItem['sellingStatus'][0]['currentPrice'][0]['__value__']
				
				currentItem = {
					'itemid' : itemId,
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
						
					currentItem['title'] = eachItem['title'][0]
					currentItem['url'] = eachItem['viewItemURL'][0]
						
					currentReport.append(currentItem)
				else:
					# if item id not in previous data, check timestamps to see if it's actually new
					currentListTime = datetime.datetime.strptime(eachItem['listingInfo'][0]['startTime'][0],'%Y-%m-%dT%H:%M:%S.000Z')

					if (previousTimestamp and previousTimeObj <= currentListTime):
						currentItem['status'] = 'NEW'
						currentItem['last_price'] = ''
						currentItem['price_difference'] = ''
						currentItem['title'] = eachItem['title'][0]
						currentItem['url'] = eachItem['viewItemURL'][0]
					
						currentReport.append(currentItem)
					
			
			currentPage = currentPage + 1
		
		# Once we've gotten through all the listings, use set operations to find removed listings
		if previousData:
			currentSkus = set([itemid for itemid in currentData])
			previousSkus = set([itemid for itemid in previousData])

			removedItems = previousSkus - currentSkus

			if removedItems:
				for itemid in removedItems:
					# Call the eBay API for each itemid to see if it returns a listing, to eliminate false positives
					currentParams = {
						'OPERATION-NAME' : 'findItemsByKeywords',
						'SERVICE-VERSION' : '1.0.0',
						'SECURITY-APPNAME' : apiKey,
						'RESPONSE-DATA-FORMAT' : 'JSON',
						'REST-PAYLOAD' : ''
						}
						
					currentParams['keywords'] = str(itemid)	
			
					r = requests.get(baseurl, params=currentParams)
					
					obj = r.json()
					
					# if the count returned is not 0, this itemid is an active listing so it wasn't removed
					if (int(obj['findItemsByKeywordsResponse'][0]['searchResult'][0]['@count']) > 0):
						continue
					
					toAdd = {
						'itemid' : itemid,
						'price' : '',
						'last_price' : previousData[itemid],
						'price_difference' : '',
						'status' : 'REMOVED',
						'title' : '',
						'url' : ''
						}
					currentReport.append(toAdd)
					
		writeOutAndClose(storeName, currentData, currentReport)
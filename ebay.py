import os
import csv
import datetime
import requests
import boto3
import logging
import openpyxl as XL
import xml.etree.ElementTree as ET

bucket = boto3.resource('s3').Bucket('ebayreports')

logger = logging.getLogger()
logger.setLevel(logging.ERROR)

storeNames = os.environ['storeNames'].split(',')
apiKey = os.environ['key']

baseurl = 'https://api.ebay.com/ws/api.dll'
	
baseparams = {
	'Content-Type' : 'text/xml',
	'X-EBAY-API-COMPATIBILITY-LEVEL' : '1081',
	'X-EBAY-API-CALL-NAME' : 'GetSellerList',
	'X-EBAY-API-SITEID' : '0'
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

pre = '{urn:ebay:apis:eBLBaseComponents}'
	
currentDate = datetime.datetime.now() - datetime.timedelta(hours=8)
future = currentDate + datetime.timedelta(days=120)

def getxml(page_number, userid):
	return """
<?xml version="1.0" encoding="utf-8"?>
<GetSellerListRequest xmlns="urn:ebay:apis:eBLBaseComponents">
	<RequesterCredentials>
    <eBayAuthToken>{}</eBayAuthToken>
  </RequesterCredentials>
  <EndTimeFrom>{}</EndTimeFrom>
  <EndTimeTo>{}</EndTimeTo>
  <Pagination>
    <EntriesPerPage>200</EntriesPerPage>
    <PageNumber>{}</PageNumber>
  </Pagination>
  <UserID>{}</UserID>
  <DetailLevel>ReturnAll</DetailLevel>
  <OutputSelector>ItemID</OutputSelector>
  <OutputSelector>Title</OutputSelector>
  <OutputSelector>PaginationResult</OutputSelector>
  <OutputSelector>SellingStatus</OutputSelector>
  <OutputSelector>ListingDetails</OutputSelector>
</GetSellerListRequest>""".format(apiKey, currentDate, future, str(page_number), userid)

def getLastRunTime(storeName):
	try:
		timestring = bucket.Object(f"{storeName}/LASTRUN").get()['Body'].read().decode('utf-8')
		return datetime.datetime.strptime(timestring, '%Y-%m-%d %H:%M:%S.%f')
	except Exception as err:
		logger.info(f"[{storeName}] Error reading LASTRUN: {err}")
		return ''
		
def getLastRunData(storeName):
	try:
		bucket.download_file(f"{storeName}/DATA", "/tmp/previousDataFile.xlsx")
		lastData_wb = XL.load_workbook(filename = "/tmp/previousDataFile.xlsx", read_only=True)
		lastData_ws = lastData_wb['Sheet']
		
		prices = {}
		titles = {}
		
		for row in lastData_ws.rows:
			prices[row[0].value] = row[1].value
			titles[row[0].value] = row[2].value
		
		bucket.Object(f"{storeName}/DATA").delete()
		return prices,titles
	except Exception as err:
		logger.error(f"[{storeName}] Error reading DATA: {err}")
		return {},{}
		
def main(event, context):
	
	for storeName in storeNames:
		previousFilename = ''
		previousData = {}
		previousData_titles {}
		previousTimestamp = ''

		currentData = {}
		currentData_titles = {}
		currentReport = []
	
		# Get timestamp of last run
		previousTimeObj = getLastRunTime(storeName)
		
		# Load previous data file into memory if it exists
		previousData,previousData_titles = getLastRunData(storeName)
		
		currentPage = 1
		totalPages = 1
		
		logger.info(f"[{storeName}] Starting...")
			
		while (currentPage <= totalPages):
			
			logger.info(f"[{storeName}] Reading page {currentPage}/{totalPages}")
			
			r = requests.post(baseurl, data=getxml(currentPage, storeName), headers=baseparams)
			
			# if error retrieving data from eBay, move to next seller
			# to avoid overwriting data file with partial data
			if (r.status_code != 200):
				logger.error(f"[{storeName}] HTTP response {r.status_code}")
				break
				
			root = ET.fromstring(r.content)
		
			totalPages = int(root.find(pre + 'PaginationResult').find(pre + 'TotalNumberOfPages').text)
	
			itemArr = root.find(pre + 'ItemArray')
				
			# loop through each item in the current page of results, add it to data, add it to report if needed
			for eachItem in itemArr:
				itemId = eachItem.find(pre + 'ItemID').text
				price = eachItem.find(pre + 'SellingStatus').find(pre + 'CurrentPrice').text
				title = eachItem.find(pre + 'Title').text
				url = eachItem.find(pre + 'ListingDetails').find(pre + 'ViewItemURL').text
				
				currentItem = {
					'itemid' : itemId,
					'price' : price,
					'title' : title,
					'url' : url
				}
						
				# add the current item to the current data set no matter what
				currentData[itemId] = price
				currentData_titles[itemId] = title
					
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
				else:
					currentItem['status'] = 'NEW'
					currentItem['last_price'] = ''
					currentItem['price_difference'] = ''
					
					currentReport.append(currentItem)
					
			currentPage = currentPage + 1
		
		# Once we've gotten through all the listings, use set operations to find removed listings
		if previousData:
			currentSkus = set([itemid for itemid in currentData])
			previousSkus = set([itemid for itemid in previousData])

			removedItems = previousSkus - currentSkus

			if removedItems:
				for itemid in removedItems:				
					toAdd = {
						'itemid' : itemid,
						'price' : '',
						'last_price' : previousData[itemid],
						'price_difference' : '',
						'status' : 'REMOVED',
						'title' : previousData_titles[itemid],
						'url' : ''
						}
					currentReport.append(toAdd)
		
		# write out the timestamp of this run
		logger.info(f"[{storeName}] Writing LASTRUN...")
		with open("/tmp/LASTRUN", 'w', newline='') as timeFile:
			timeFile.write(f"{currentDate}")
	
		# write out the data
		logger.info(f"[{storeName}] Writing DATA.xlsx...")
		wb_data = XL.Workbook()
		ws_data = wb_data.active
		
		for itemid in currentData:
			ws_data.append([itemid, currentData[itemid], currentData_titles[itemid]])
			
		wb_data.save("/tmp/DATA.xlsx")
					
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
		bucket.Object(f"{storeName}/DATA").put(Body=open(f"/tmp/DATA.xlsx", 'rb'))
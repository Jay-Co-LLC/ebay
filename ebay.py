import os
import datetime
import requests
import boto3
import logging
import openpyxl as XL
import xml.etree.ElementTree as ET

BUCKET = boto3.resource('s3').Bucket('ebayreports')

LOG = logging.getLogger()
LOG.setLevel(logging.ERROR)

STORE_NAMES = os.environ['storeNames'].split(',')
KEY = os.environ['key']

URL = 'https://api.ebay.com/ws/api.dll'
	
HEADERS = {
	'Content-Type' : 'text/xml',
	'X-EBAY-API-COMPATIBILITY-LEVEL' : '1081',
	'X-EBAY-API-CALL-NAME' : 'GetSellerEvents',
	'X-EBAY-API-SITEID' : '0'
	}
	
REPORT_FIELDS = [
	'itemid',
	'status',
	'title',
	'price',
	'last_price',
	'price_difference',
	'url'
	]

PRE = '{urn:ebay:apis:eBLBaseComponents}'
	
TODAY = datetime.datetime.now() - datetime.timedelta(hours=8)
TODAY_STRING = TODAY.strftime('%m-%d-%Y %I:%M%p')

DATE_TYPE_MOD = 'Mod'
DATE_TYPE_NEW = 'Start'
DATE_TYPE_REM = 'End'

FN_LASTRUN = 'lastrun.txt'
FN_DATA = 'data.xlsx'
FN_REPORT = 'report.xlsx'

def P(str):
	return f'{PRE}{str}'

def getxml(storeName, fromDate, toDate, dateType):
	return f"""
<?xml version="1.0" encoding="utf-8"?>
<GetSellerEventsRequest xmlns="urn:ebay:apis:eBLBaseComponents">
	<RequesterCredentials>
    <eBayAuthToken>{apiKey}</eBayAuthToken>
  </RequesterCredentials>
  <{dateType}TimeFrom>{fromDate}</{dateType}TimeFrom>
  <{dateType}TimeTo>{toDate}</{dateType}TimeTo>
  <UserID>{storeName}</UserID>
  <DetailLevel>ReturnAll</DetailLevel>
  <OutputSelector>ItemID</OutputSelector>
  <OutputSelector>ListingDetails</OutputSelector>
  <OutputSelector>SellingStatus</OutputSelector>
</GetSellerEventsRequest>"""

def getLastRunTime(storeName):
	try:
		timestring = bucket.Object(f"{storeName}/{FN_LASTRUN}").get()['Body'].read().decode('utf-8')
		return datetime.datetime.strptime(timestring, '%Y-%m-%dT%H:%M:%S.%fZ')
	except Exception as err:
		LOG.info(f"[{storeName}] Error reading {FN_LASTRUN}: {err}")
		return ''
		
def getLastRunData(storeName):
	try:
		bucket.download_file(f"{storeName}/{FN_DATA}", "/tmp/{storeName}/{FN_DATA}")
		lastData_wb = XL.load_workbook(filename = "/tmp/{storeName}/{FN_DATA}", read_only=True)
		lastData_ws = lastData_wb['Sheet']
		
		items = {}
		
		for row in lastData_ws.rows:
			items[row[0].value] = row[1].value
			
		return items
	except Exception as err:
		LOG.error(f"[{storeName}] Error reading {FN_DATA}: {err}")
		return {}
		
def getListings(storeName, previousTimestamp, dateType):
	body = getxml(storeName, previousTimestamp, TODAY, dateType)
	res = requests.post(URL, data=body, headers=HEADERS)
	root = ET.fromstring(res.content)
	itemList = root.find(P('ItemArray'))
	return itemList
	
def putToS3(remoteName, localName):
	BUCKET.Object(remoteName).put(Body=open(localName, 'rb'))
		
def main(event, context):
	
	for storeName in STORE_NAMES:
		data = getLastRunData(storeName)
		
		# Move to next store if we can't retrieve data
		if (not previousData):
			continue
			
		previousTimestamp = getLastRunTime(storeName)

		report = []
		
		modListings = getListings(storeName, previousTimestamp, DATE_TYPE_MOD)
		newListings = getListings(storeName, previousTimestamp, DATE_TYPE_NEW)
		endListings = getListings(storeName, previousTimestamp, DATE_TYPE_REM)
		
		if (modListings):
			# loop through modListings
			# compare price
			# if different, add to report, update previousData
			
		if (newListings):
			# loop through newListings
			# add to report and data
			
		if (endListings):
			# loop through endListings
			# add to report and remove from data
				
		# write out the timestamp of this run
		LOG.info(f"[{storeName}] Writing LASTRUN...")
		with open("/tmp/{storeName}/{FN_LASTRUN}", 'w', newline='') as timeFile:
			timeFile.write(f"{TODAY}")
	
		# write out the data
		LOG.info(f"[{storeName}] Writing DATA...")
		wb_data = XL.Workbook()
		ws_data = wb_data.active
		
		for itemid in data:
			ws_data.append([itemid, data[itemid])
			
		wb_data.save("/tmp/{storeName}/{FN_DATA}")
					
		# write out the report
		if report:
			logger.info(f"[{storeName}] Writing REPORT...")
			wb = XL.Workbook()
			ws = wb.active
			ws.append(REPORT_FIELDS)
			
			for eachItem in report:
				ws.append([eachItem[field] for field in REPORT_FIELDS])
				
			wb.save("/tmp/{storeName}/{FN_REPORT}")
			
			reportName = f"REPORT - {storeName} - {TODAY_STRING}.xlsx"
			putToS3(reportName, f"/tmp/{storeName}/{FN_REPORT}")

		putToS3(f"{storeName}/{FN_LASTRUN}", f"/tmp/{storeName}/{FN_LASTRUN}")
		putToS3(f"{storeName}/{FN_DATA}", f"/tmp/{storeName}/{FN_DATA}")
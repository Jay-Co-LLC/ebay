import os
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
	'X-EBAY-API-CALL-NAME' : 'GetSellerEvents',
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
	
today = datetime.datetime.now() - datetime.timedelta(hours=8)
future = today + datetime.timedelta(days=120)

def getxml(userid):
	return """
<?xml version="1.0" encoding="utf-8"?>
<GetSellerEventsRequest xmlns="urn:ebay:apis:eBLBaseComponents">
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
  <
  <OutputSelector>SellingStatus</OutputSelector>
</GetSellerEventsRequest>""".format(apiKey, today, future, str(page_number), userid)

def getLastRunTime(storeName):
	try:
		timestring = bucket.Object(f"{storeName}/lastrun.txt").get()['Body'].read().decode('utf-8')
		return datetime.datetime.strptime(timestring, '%Y-%m-%dT%H:%M:%S.%fZ')
	except Exception as err:
		logger.info(f"[{storeName}] Error reading lastrun.txt: {err}")
		return ''
		
def getLastRunData(storeName):
	try:
		bucket.download_file(f"{storeName}.xlsx", "/tmp/{storName}.xlsx")
		lastData_wb = XL.load_workbook(filename = "/tmp/{storeName}.xlsx", read_only=True)
		lastData_ws = lastData_wb['Sheet']
		
		items = {}
		
		for row in lastData_ws.rows:
			items[row[0].value] = row[1].value
			
		return items
	except Exception as err:
		logger.error(f"[{storeName}] Error reading DATA: {err}")
		return {}
		
def getModifiedListings(storeName):
	previousTimestamp = getLastRunTime(storeName)
	r = requests.post(baseurl, data=getxml(storeName), headers=baseparams)
	
		
def main(event, context):
	
	for storeName in storeNames:
		previousData = getLastRunData(storeName)

		currentReport = []
		
		# modListings = getModifiedListings(storeName)
		# newListings = getNewListings(storeName)
		# endListings = getEndedListings(storeName)
				
		r = requests.post(baseurl, data=getxml(currentPage, storeName), headers=baseparams)
					
		root = ET.fromstring(r.content)
		itemList = root.find(pre + 'ItemArray')
		
		for eachItem in itemList:
			continue
				
		# write out the timestamp of this run
		logger.info(f"[{storeName}] Writing LASTRUN...")
		with open("/tmp/LASTRUN", 'w', newline='') as timeFile:
			timeFile.write(f"{today}")
	
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
			
			bucket.Object(f"{storeName}/REPORT - {storeName} - {today.strftime('%m-%d-%Y %I:%M%p')}.xlsx").put(Body=open("/tmp/REPORT.xlsx", 'rb'))

		bucket.Object(f"{storeName}/LASTRUN").put(Body=open("/tmp/LASTRUN", 'rb'))	
		bucket.Object(f"{storeName}/DATA").put(Body=open(f"/tmp/DATA.xlsx", 'rb'))
import config
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

obj = r.json()
pageInfo = obj['findItemsIneBayStoresResponse'][0]['paginationOutput'][0]

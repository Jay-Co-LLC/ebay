import config
import requests

baseurl = 'https://svcs.ebay.com/services/search/FindingService/v1'

params = {
	'OPERATION-NAME' : 'findItemsIneBayStores',
	'SERVICE-VERSION' : '1.0.0',
	'SECURITY-APPNAME' : config.key,
	'RESPONSE-DATA-FORMAT' : 'JSON',
	'REST-PAYLOAD' : '',
	'storeName' : 'Suspension Specialists'
	}
	
r = requests.get(baseurl, params=params)

print(r.status_code)
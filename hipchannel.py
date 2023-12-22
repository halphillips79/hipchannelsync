import requests
import json
import datetime
import logging

logging.basicConfig(filename='sync_log.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

try:
    with open('config.json', 'r') as f:
        config = json.load(f)
    logging.info("Successfully read the config.json file.")
except FileNotFoundError as e:
    logging.error("Missing config.json file.")
    exit(1)

required_keys = [
    "CHANNEL_ADVISOR_API_ENDPOINT", 
    "HIPSTAMP_API_ENDPOINT",
    "CHANNEL_ADVISOR_DEVELOPER_KEY", 
    "HIPSTAMP_API_KEY",
    "LAST_CHECKED_FILE_HIP",
    "LAST_CHECKED_FILE_CA",
    "CHANNEL_ADVISOR_CLIENT_ID",
    "CHANNEL_ADVISOR_CLIENT_SECRET",
    "CHANNEL_ADVISOR_REFRESH_TOKEN",
    "HIPSTAMP_USERNAME"
]

for key in required_keys:
    if key not in config:
        logging.error(f"Missing {key} in config.json")
        exit(1)

# Constants from config
CHANNEL_ADVISOR_API_ENDPOINT = config["CHANNEL_ADVISOR_API_ENDPOINT"]
HIPSTAMP_API_ENDPOINT = config["HIPSTAMP_API_ENDPOINT"]
CHANNEL_ADVISOR_DEVELOPER_KEY = config["CHANNEL_ADVISOR_DEVELOPER_KEY"]
HIPSTAMP_API_KEY = config["HIPSTAMP_API_KEY"]
LAST_CHECKED_FILE_HIP = config["LAST_CHECKED_FILE_HIP"]
LAST_CHECKED_FILE_CA = config["LAST_CHECKED_FILE_CA"]
CHANNEL_ADVISOR_CLIENT_ID = config["CHANNEL_ADVISOR_CLIENT_ID"]
CHANNEL_ADVISOR_CLIENT_SECRET = config["CHANNEL_ADVISOR_CLIENT_SECRET"]
CHANNEL_ADVISOR_REFRESH_TOKEN = config["CHANNEL_ADVISOR_REFRESH_TOKEN"]
HIPSTAMP_USERNAME = config["HIPSTAMP_USERNAME"]

def log_current_hipstamp_inventory():
    url = f"{HIPSTAMP_API_ENDPOINT}/stores/{HIPSTAMP_USERNAME}/listings/active"
    headers = {
        "Content-Type": "application/json",
        "X-ApiKey": HIPSTAMP_API_KEY,
    }
    try:
        response = requests.get(url, headers=headers)
        logging.info(f"HipStamp request URL: {response.url}")
        response.raise_for_status()
        with open('hipstamp_inventory_backup.json', 'w') as f:
            json.dump(response.json(), f)
        logging.info("Successfully logged current HipStamp inventory.")
    except requests.RequestException as e:
        logging.error(f"Failed to log current HipStamp inventory: {e}")
        logging.error(f"Response content: {response.content}")
        logging.error(f"Status code: {response.status_code}")

def log_current_channeladvisor_inventory(access_token):
    url = f"{CHANNEL_ADVISOR_API_ENDPOINT}/v1/Products"
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        with open('channeladvisor_inventory_backup.json', 'w') as f:
            json.dump(response.json(), f)
        logging.info("Successfully logged current ChannelAdvisor inventory.")
    except requests.RequestException as e:
        logging.error(f"Failed to log current ChannelAdvisor inventory: {e}")

def get_last_checked_time(file_name):
    try:
        with open(file_name, "r") as f:
            last_time = f.read().strip()
        logging.info(f"Successfully read last checked time from {file_name}: {last_time}")
        return last_time
    except FileNotFoundError:
        logging.warning(f"{file_name} not found. Setting last checked time to None.")
        return None

def update_last_checked_time(file_name):
    current_time = datetime.datetime.now().isoformat()
    with open(file_name, "w") as f:
        f.write(current_time)
    logging.info(f"Updated last checked time in {file_name} to {current_time}.")

def fetch_hipstamp_sales(last_checked_time):
    formatted_time = datetime.datetime.fromisoformat(last_checked_time).strftime('%Y-%m-%dT%H:%M:%SZ')
    url = f"{HIPSTAMP_API_ENDPOINT}/stores/{HIPSTAMP_USERNAME}/sales/paid?created_time_from={formatted_time}"
    headers = {
        "Content-Type": "application/json",
        "X-ApiKey": HIPSTAMP_API_KEY,
    }
    try:
        response = requests.get(url, headers=headers)
        print(response.url)
        response.raise_for_status()
        sales_data = response.json()
        if not all('SaleListings' in sale for sale in sales_data.get('results', [])):
            logging.error("Some sale objects do not contain 'SaleListings'.")
            return None

        for sale in sales_data.get('results', []):
            for listing in sale.get('SaleListings', []):
                listing['title'] = listing.pop('listing_name', None)
        logging.info(f"HipStamp sales response: {sales_data}")
        return sales_data
    except requests.RequestException as e:
        logging.error(f"Error fetching HipStamp sales: {e}")
        return None

def fetch_channeladvisor_sales(last_checked_time_ca, access_token):
    formatted_time = datetime.datetime.fromisoformat(last_checked_time_ca).strftime('%Y-%m-%dT%H:%M:%SZ')
    url = f"{CHANNEL_ADVISOR_API_ENDPOINT}/v1/Orders"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {
        '$filter': f'CreatedDateUtc ge {formatted_time}',
        '$expand': 'Items'
    }
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        sales_data = response.json()
        logging.info(f"ChannelAdvisor sales data fetched: {sales_data}")
        return sales_data
    except requests.RequestException as e:
        logging.error(f"Error fetching ChannelAdvisor sales: {e}")
        return None

def update_channeladvisor_quantity(sale_listings, access_token):
    headers = {"Authorization": f"Bearer {access_token}"}
    for listing in sale_listings:
        product_title = listing.get('title', '')
        try:
            sold_quantity = listing['quantity']
        except KeyError:
            logging.error(f"'quantity' key missing from listing. Full listing data: {listing}")
            continue

        if isinstance(sold_quantity, str):
            try:
                sold_quantity = int(sold_quantity)
            except ValueError:
                logging.error(f"Failed to convert sold_quantity to int. Original value: {sold_quantity}")
                continue
        elif not isinstance(sold_quantity, (int, float)):
            logging.error(f"Unexpected data type for sold_quantity. Expected int or float, got {type(sold_quantity)} with value: {sold_quantity}")
            continue

        # Step 1: Look up the product by title
        url_lookup = f"{CHANNEL_ADVISOR_API_ENDPOINT}/v1/Products"
        replaced_title = product_title.replace("'", "''")
        params = {'$filter': f"Title eq '{replaced_title}'"}
        try:
            response_lookup = requests.get(url_lookup, headers=headers, params=params)
            response_lookup.raise_for_status()
            products = response_lookup.json().get('value', [])
            if len(products) == 0:
                logging.warning(f"No matching product found in ChannelAdvisor for product '{product_title}'. Did not decrement.[DISPLAY]")
                continue
            elif len(products) > 1:
                logging.warning(f"Multiple matching products found in ChannelAdvisor for product '{product_title}'. Did not decrement.[DISPLAY]")
                continue
            product_id = products[0]['ID']
        except requests.RequestException as e:
            logging.error(f"Error looking up product by title in ChannelAdvisor: {e}[DISPLAY]")
            continue

        # Step 2: Update the product quantity
        url_update = f"{CHANNEL_ADVISOR_API_ENDPOINT}/v1/Products({product_id})/UpdateQuantity"
        payload = {
            "Value": {
                "UpdateType": "UnShipped",
                "CompleteDCList": "False",
                "Updates": [
                    {
                        "DistributionCenterID": 0,
                        "Quantity": -sold_quantity
                    }
                ]
            }
        }
        try:
            response = requests.post(url_update, headers=headers, json=payload)
            response.raise_for_status()
            logging.info(f"Updated ChannelAdvisor inventory for product {product_title}. Decremented by {sold_quantity}.[DISPLAY]")
        except requests.RequestException as e:
            logging.error(f"Failed to update ChannelAdvisor inventory for product {product_title}: {e}[DISPLAY]")

def update_hipstamp_quantity(sale_listings):
    for listing in sale_listings:
        for item in listing.get('Items', []):
            new_quantity = item['Quantity']
            product_title = item.get('Title', '')

            # Step 1: Look up the product by title
            url_check = f"{HIPSTAMP_API_ENDPOINT}/stores/{HIPSTAMP_USERNAME}/listings/active?keywords={product_title}"
            params_check = {'api_key': HIPSTAMP_API_KEY}
            try:
                response_check = requests.get(url_check, params=params_check)
                response_check.raise_for_status()
                response_data = response_check.json()
                if response_data['count'] == 0:
                    logging.error(f"No matching product found in HipStamp for product {product_title}.[DISPLAY]")
                    logging.error(f"Full response: {response_data}")
                    continue
                elif response_data['count'] > 1:
                    logging.error(f"Multiple matching products found in HipStamp for product {product_title}.[DISPLAY]")
                    logging.error(f"Full response: {response_data}")
                    continue
                else:
                    listing_id = response_data['results'][0]['id']
                    current_quantity = response_data['results'][0]['quantity']
                    updated_quantity = int(current_quantity) - new_quantity    
                    logging.info(f"Successfully matched product in HipStamp: {product_title}.")
                    if updated_quantity < 0:
                        logging.error(f"Error: Updated quantity for {product_title} is negative. Skipping update.[DISPLAY]")
                        continue
            except requests.RequestException as e:
                logging.error(f"Error checking product existence in HipStamp for product {product_title}: {e}[DISPLAY]")
                continue

            # Step 2: Update the product quantity
            url = f"{HIPSTAMP_API_ENDPOINT}/listings/{listing_id}"
            params = {
                'api_key': HIPSTAMP_API_KEY,
                'id': listing_id,
                'quantity': updated_quantity
            }
            try:
                response = requests.put(url, params=params)
                response.raise_for_status()
                logging.info(f"Updated HipStamp inventory for product {product_title}. Decremented by {new_quantity}.[DISPLAY]")
            except requests.RequestException as e:
                logging.error(f"Failed to update HipStamp inventory for product {product_title}: {e}[DISPLAY]")

def get_access_token():
    url = "https://api.channeladvisor.com/oauth2/token"
    data = {
        "grant_type": "refresh_token",
        "refresh_token": CHANNEL_ADVISOR_REFRESH_TOKEN,
        "client_id": CHANNEL_ADVISOR_CLIENT_ID,
        "client_secret": CHANNEL_ADVISOR_CLIENT_SECRET
    }
    try:
        response = requests.post(url, data=data)
        response.raise_for_status()
        json_response = response.json()
        if 'access_token' in json_response:
            return json_response["access_token"]
        else:
            logging.error("Missing access_token in API response.")
            return None

    except requests.RequestException as e:
        logging.error(f"Failed to get ChannelAdvisor access token: {e}")
        logging.error(f"Response content: {response.content}")
        return None

def validate_response(response_json, expected_keys, source_name):
    for key in expected_keys:
        if key not in response_json:
            logging.error(f"Missing key {key} in {source_name} API response")
            return False
    return True

def main():
    access_token = get_access_token()
    if access_token is None:
        logging.error("Terminating script due to unsuccessful token retrieval.")
        exit(1)

    log_current_hipstamp_inventory()
    log_current_channeladvisor_inventory(access_token)

    # HipStamp to ChannelAdvisor sync
    last_checked_time_hip = get_last_checked_time(LAST_CHECKED_FILE_HIP)
    sales_data_hip = fetch_hipstamp_sales(last_checked_time_hip)
    if sales_data_hip is not None and validate_response(sales_data_hip, ['results'], 'HipStamp'):
        num_sales = len(sales_data_hip.get('results', []))
        logging.info(f"{num_sales} new sales fetched from HipStamp since {last_checked_time_hip}") 
        for sale in sales_data_hip.get('results', []):
            if 'SaleListings' in sale:
                update_channeladvisor_quantity(sale.get('SaleListings', []), access_token)
        update_last_checked_time(LAST_CHECKED_FILE_HIP)
    else:
        logging.warning("Failed to fetch HipStamp sales data.")
    
    # ChannelAdvisor to HipStamp sync
    last_checked_time_ca = get_last_checked_time(LAST_CHECKED_FILE_CA)
    sales_data_ca = fetch_channeladvisor_sales(last_checked_time_ca, access_token)
    if sales_data_ca is not None and validate_response(sales_data_ca, ['value'], 'ChannelAdvisor'):
        list_of_sales = sales_data_ca.get('value', [])
        num_sales = len(list_of_sales)
        logging.info(f"{num_sales} new sales fetched from ChannelAdvisor since {last_checked_time_ca}")
        update_hipstamp_quantity(list_of_sales)
        update_last_checked_time(LAST_CHECKED_FILE_CA)
    else:
        logging.warning("Failed to fetch ChannelAdvisor sales data.")

if __name__ == "__main__":
    main()
#### Librerias
import requests
import hmac
import hashlib
import time
import os
import json
import dash
from dash import html, dcc, Input, Output, State
import dash_bootstrap_components as dbc


#### Conectividad
BINANCE_API_KEY = os.getenv('BINANCE_API_KEY')
BINANCE_API_SECRET = os.getenv('BINANCE_SECRET_KEY')
PIN = os.getenv('PIN')

BASE_URL = "https://api.binance.com"

#### Funciones
def ping_binance():
    """Ping Binance API to check the connectivity."""
    url = f"{BASE_URL}/api/v3/ping"
    response = requests.get(url, headers=headers())
    if response.status_code == 200:
        print("Connection successful.")
    else:
        print(f"Connection failed with status code: {response.status_code}")


# Function to get the server time
def get_server_time():
    url = BASE_URL + "/api/v3/time"
    response = requests.get(url)
    server_time = response.json().get('serverTime')
    return server_time

# Function to calculate the drift between local and server time
def get_time_drift():
    local_timestamp = int(time.time() * 1000)
    server_timestamp = get_server_time()
    return server_timestamp - local_timestamp

# Function to get the adjusted timestamp
def get_adjusted_timestamp():
    drift = get_time_drift()

    adjusted_timestamp = int(time.time() * 1000) + drift
    return adjusted_timestamp

def sign_request(data):
    query_string = '&'.join([f"{key}={value}" for key, value in data.items()])
    signature = hmac.new(BINANCE_API_SECRET.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
    return signature

def headers():
    return {
        'X-MBX-APIKEY': BINANCE_API_KEY,
        'Content-Type': 'application/x-www-form-urlencoded'
    }

def place_market_order(symbol, quantity, side):
    """Place a market order."""
    params = {
        'symbol': symbol,
        'side': side,
        'type': 'MARKET',
        'quantity': quantity,
        'timestamp': get_adjusted_timestamp()
    }
    params['signature'] = sign_request(params)
    url = BASE_URL + "/api/v3/order"
    response = requests.post(url, headers=headers(), params=params)
    if response.status_code == 200:
        print("Order placed successfully:", response.json())
    else:
        print("Failed to place order. Response:", response.json())
    return response.json()

def place_limit_order(symbol, quantity, price, side):
    """Place a limit order."""
    params = {
        'symbol': symbol,
        'side': side,
        'type': 'LIMIT',
        'timeInForce': 'GTC',  # Good Till Cancelled
        'quantity': quantity,
        'price': str(price),
        'timestamp': get_adjusted_timestamp()
    }
    params['signature'] = sign_request(params)
    url = BASE_URL + "/api/v3/order"
    response = requests.post(url, headers=headers(), params=params)
    if response.status_code == 200:
        print("Limit order placed successfully:", response.json())
    else:
        print("Failed to place limit order. Response:", response.json())
    return response.json()

def place_oco_order(symbol, quantity, price, stop_price, stop_limit_price, side):
    """Place an OCO order."""
    params = {
        'symbol': symbol,
        'side': side,
        'quantity': quantity,
        'price': str(price),  # Limit (take profit) price
        'stopPrice': str(stop_price),  # Stop Loss trigger price
        'stopLimitPrice': str(stop_limit_price),  # Price at which the stop limit order is executed
        'stopLimitTimeInForce': 'GTC',
        'timestamp': get_adjusted_timestamp()
    }
    params['signature'] = sign_request(params)
    url = BASE_URL + "/api/v3/order/oco"
    response = requests.post(url, headers=headers(), params=params)
    if response.status_code == 200:
        print("OCO order placed successfully: quantity:", quantity)
    else:
        print("Failed to place OCO order. Response:", response.json())
    return response.json()



def get_usdt_balance():
    params = {
        'timestamp': get_adjusted_timestamp()
    }
    params['signature'] = sign_request(params)
    url = f"{BASE_URL}/api/v3/account"
    response = requests.get(url, headers=headers(), params=params)
    if response.status_code == 200:
        balances = response.json().get('balances', [])
        usdt_balance = next((item for item in balances if item["asset"] == "USDT"), None)
        return float(usdt_balance['free']) if usdt_balance else 0
    else:
        print(f"Failed to fetch balance, HTTP status code: {response.status_code}")
        print("Response:", response.json())
        return None

def oco_short_btcusdt(target_price, stop_price):
    usdt_balance = get_usdt_balance()
    btc_limit = usdt_balance/target_price
    btc_stop = usdt_balance/stop_price
    if usdt_balance > 0:
        print(round(btc_stop*0.99, 5))
        response = place_oco_order('BTCUSDT', round(btc_stop*0.99,5), f'{target_price}', f'{stop_price}', f'{stop_price+100}', 'BUY')
        print("Market order result:", response)
    else:
        print("Insufficient USDT balance to place market order.")
    return response.json()



## 3.5
def get_all_balances():
    params = {
        'timestamp': get_adjusted_timestamp()
    }
    params['signature'] = sign_request(params)
    url = f"{BASE_URL}/api/v3/account"
    response = requests.get(url, headers=headers(), params=params)
    if response.status_code == 200:
        balances = response.json().get('balances', [])
        return balances
    else:
        print(f"Failed to fetch balances, HTTP status code: {response.status_code}")
        print("Response:", response.json())
        return []
    
def get_last_price(asset, base='USDT'):
    url = f"{BASE_URL}/api/v3/ticker/price"
    params = {'symbol': f"{asset}{base}"}
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return float(response.json()['price'])
    else:
        print(f"Failed to fetch last price for {asset}. HTTP status code: {response.status_code}")
        return None
#############################################

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.CYBORG])  # Using a dark theme


app.layout = dbc.Container([
    dbc.Row([
        dbc.Col(html.H1("LuMaLu Trader"), width=12),
    ]),
    dbc.Row(dbc.Col(dcc.Input(id='pin-input', type='password', placeholder='Enter PIN', className='mb-2'), width=12)),
    dbc.Row([
        dbc.Col([
            html.H2("Market Orders"),
            dcc.Input(id='market-symbol-input', type='text', placeholder='Symbol (e.g., BTCUSDT)', className='mb-2'),
            dcc.Input(id='market-quantity-input', type='number', placeholder='Quantity', className='mb-2'),
            html.Button('Buy Market Order', id='buy-market-order-button', n_clicks=0, className='btn btn-primary mb-2'),
            html.Button('Sell Market Order', id='sell-market-order-button', n_clicks=0, className='btn btn-danger mb-2'),
            html.Div(id='market-output-container', className='text-light')
        ], width=4),
        dbc.Col([
            html.H2("Limit Orders"),
            dcc.Input(id='limit-symbol-input', type='text', placeholder='Symbol', className='mb-2'),
            dcc.Input(id='limit-quantity-input', type='number', placeholder='Quantity', className='mb-2'),
            dcc.Input(id='limit-price-input', type='number', placeholder='Price', className='mb-2'),
            html.Button('Buy Limit Order', id='buy-limit-order-button', n_clicks=0, className='btn btn-primary mb-2'),
            html.Button('Sell Limit Order', id='sell-limit-order-button', n_clicks=0, className='btn btn-danger mb-2'),
            html.Div(id='limit-output-container', className='text-light')
        ], width=4),
        dbc.Col([
            html.H2("OCO Short Orders"),
            dcc.Input(id='oco-target-price-input', type='number', placeholder='Target Price', className='mb-2'),
            dcc.Input(id='oco-stop-price-input', type='number', placeholder='Stop Price', className='mb-2'),
            html.Button('OCO Short BTCUSD', id='oco-order-button', n_clicks=0, className='btn btn-warning'),
            html.Div(id='oco-output-container', className='text-light')
        ], width=4)
    ]),
    dbc.Row([
        dbc.Col([
            html.H2("Balances"),
            html.Div(id='balances-table'),
            dcc.Graph(id='balances-pie-chart')
        ])
    ]),
    dcc.Interval(
        id='interval-component',
        interval=60 * 1000,  # in milliseconds
        n_intervals=0
    )
], fluid=True, className='bg-dark') 

# Callbacks for market orders
@app.callback(
    Output('market-output-container', 'children'),
    [Input('buy-market-order-button', 'n_clicks'),
     Input('sell-market-order-button', 'n_clicks')],
    [State('market-symbol-input', 'value'),
     State('market-quantity-input', 'value'),
     State('pin-input', 'value')]
)
def handle_market_order(buy_clicks, sell_clicks, symbol, quantity, pin):
    ctx = dash.callback_context
    if not ctx.triggered:
        return ""
    else:
        button_id = ctx.triggered[0]['prop_id'].split('.')[0]
        if pin == PIN:
            if button_id == "buy-market-order-button":
                response = place_market_order(symbol, quantity, 'BUY')
            elif button_id == "sell-market-order-button":
                response = place_market_order(symbol, quantity, 'SELL')
            return f"Market Order Response: status: {response['status']}, side: {response['side']}, qty: {response['executedQty']}"
        return "Invalid PIN or no action taken."

# Callbacks for limit orders
@app.callback(
    Output('limit-output-container', 'children'),
    [Input('buy-limit-order-button', 'n_clicks'),
     Input('sell-limit-order-button', 'n_clicks')],
    [State('limit-symbol-input', 'value'),
     State('limit-quantity-input', 'value'),
     State('limit-price-input', 'value'),
     State('pin-input', 'value')]
)
def handle_limit_order(buy_clicks, sell_clicks, symbol, quantity, price, pin):
    ctx = dash.callback_context
    if not ctx.triggered:
        return ""
    else:
        button_id = ctx.triggered[0]['prop_id'].split('.')[0]
        if pin == PIN:
            if button_id == "buy-limit-order-button":
                response = place_limit_order(symbol, quantity, price, 'BUY')
            elif button_id == "sell-limit-order-button":
                response = place_limit_order(symbol, quantity, price, 'SELL')
            return f"Limit Order Response: status: {response['status']}, side: {response['side']}, qty: {response['origQty']}"
        return "Invalid PIN or no action taken."
# callback OCO orders
@app.callback(
    Output('oco-output-container', 'children'),
    Input('oco-order-button', 'n_clicks'),
    #State('oco-symbol-input', 'value'),
    State('oco-target-price-input', 'value'),
    State('oco-stop-price-input', 'value'),
    State('pin-input', 'value')
)
def handle_oco_order(n_clicks, target_price, stop_price, pin, symbol=None):
    if n_clicks > 0 and pin == PIN:
        response = oco_short_btcusdt(target_price, stop_price)
        return f"OCO Order Response: status: {response['status']}, side: {response['side']}, qty: {response['origQty']}"



######### 3.5
# Implement callback to update the table and pie chart with fetched balances
@app.callback(
    Output('balances-table', 'children'),
    Output('balances-pie-chart', 'figure'),
    Input('interval-component', 'n_intervals')
)
def update_balances_table_and_chart(n_intervals):
    balances = get_all_balances()
    print("Balances:", balances) 
    if balances:
        # Filter balances with non-zero values
        balances = [balance for balance in balances if float(balance['free']) > 0]

        # Prepare table data
        table_data = []
        for balance in balances:
            table_data.append(html.Tr([
                html.Td(balance['asset']),
                html.Td(balance['free']),
                html.Td(balance['locked'])
            ]))
        table = dbc.Table([
            html.Thead([
                html.Tr([
                    html.Th("Asset"),
                    html.Th("Free"),
                    html.Th("Locked")
                ])
            ]),
            html.Tbody(table_data)
        ], bordered=True, striped=True, hover=True, responsive=True)

        # Prepare pie chart data
        labels = [balance['asset'] for balance in balances]
        values = [float(balance['free']) for balance in balances]
        # Normalize balances in USDT
        usdt_prices = {asset: get_last_price(asset) for asset in labels}
        print("Downloaded values for each coin:")
        for asset, price in usdt_prices.items():
            print(f"{asset}: {price}")
        # Fallback mechanism for fetching last price
        for asset in labels:
            if asset not in usdt_prices:
                # Use a default value or skip normalization for the asset
                usdt_prices[asset] = 1  # Defaulting to 1 for now
        # Ignore assets with failed last price fetch or 'ETHW'
        usdt_prices = {asset: price for asset, price in usdt_prices.items() if price is not None and asset != 'ETHW'}
        # Normalize balances in USDT for assets with available prices
        values_in_usdt = [value * usdt_prices[asset] for value, asset in zip(values, labels) if asset in usdt_prices]
        print("Pie Chart Labels:", labels)  # Check if labels are retrieved correctly
        print("Pie Chart Values in USDT:", values_in_usdt)  # Check if values are normalized correctly
        pie_chart = {
            'data': [
                {'labels': labels, 'values': values_in_usdt, 'type': 'pie'}
            ],
            'layout': {
                'title': 'Asset Balances'
            }
        }

        return table, pie_chart

    return dash.no_update, dash.no_update



################
if __name__ == '__main__':
    app.run_server(os.getenv("HOST", "0.0.0.0"), port=os.getenv("PORT", 8080))

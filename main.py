import requests
import hmac
import hashlib
import time
import os
import dash
from dash import html, dcc, Output, Input, State
import dash_bootstrap_components as dbc

# Conectividad
BINANCE_API_KEY = os.getenv('BINANCE_API_KEY')
BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET')
PIN = os.getenv('PIN')

# Debugging: print environment variables to ensure they are set correctly
print(f"BINANCE_API_KEY: {BINANCE_API_KEY}")
print(f"BINANCE_API_SECRET: {BINANCE_API_SECRET}")
print(f"PIN: {PIN}")

BASE_URL = "https://api.binance.com"

def headers():
    return {
        'X-MBX-APIKEY': BINANCE_API_KEY,
        'Content-Type': 'application/x-www-form-urlencoded'
    }

def get_adjusted_timestamp():
    drift = get_time_drift()
    adjusted_timestamp = int(time.time() * 1000) + drift
    print(f"Adjusted Timestamp: {adjusted_timestamp}")  # Debugging
    return adjusted_timestamp

def get_time_drift():
    local_timestamp = int(time.time() * 1000)
    server_timestamp = get_server_time()
    drift = server_timestamp - local_timestamp
    print(f"Time Drift: {drift}")  # Debugging
    return drift

def get_server_time():
    url = BASE_URL + "/api/v3/time"
    response = requests.get(url)
    server_time = response.json().get('serverTime')
    print(f"Server Time: {server_time}")  # Debugging
    return server_time

def sign_request(data):
    query_string = '&'.join([f"{key}={value}" for key, value in data.items()])
    if BINANCE_API_SECRET is None:
        raise ValueError("BINANCE_API_SECRET is not set")
    signature = hmac.new(BINANCE_API_SECRET.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
    print(f"Signature: {signature}")  # Debugging
    return signature

def place_market_order(symbol, quantity, side):
    params = {
        'symbol': symbol,
        'side': side,
        'type': 'MARKET',
        'quantity': quantity,
        'timestamp': get_adjusted_timestamp()
    }
    params['signature'] = sign_request(params)
    url = BASE_URL + "/api/v3/order"
    try:
        response = requests.post(url, headers=headers(), params=params)
        response.raise_for_status()
        print("Order placed successfully:", response.json())
    except requests.exceptions.RequestException as e:
        print(f"Failed to place order. Exception: {e}")
        if response:
            print("Response:", response.json())
    return response.json()

def place_limit_order(symbol, quantity, price, side):
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
    try:
        response = requests.post(url, headers=headers(), params=params)
        response.raise_for_status()
        order_response = response.json()
        print("Limit order placed successfully:", order_response)
        return order_response
    except requests.exceptions.RequestException as e:
        print(f"Failed to place limit order. Exception: {e}")
        if response is not None:
            print("Response:", response.json())
        return {"error": str(e)}




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
    try:
        response = requests.post(url, headers=headers(), params=params)
        response.raise_for_status()
        order_response = response.json()
        print("OCO order placed successfully:", order_response)
        return order_response
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
        print("Response:", response.json())
        return response.json()
    except Exception as e:
        print(f"An error occurred: {e}")
        return {"error": str(e)}


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
    btc_stop = usdt_balance / stop_price
    if usdt_balance > 0:
        print(round(btc_stop * 0.99, 5))
        result = place_oco_order('BTCUSDT', round(btc_stop * 0.99, 5), f'{target_price}', f'{stop_price}', f'{stop_price + 100}', 'BUY')
        print("Market order result:", result)
        return result
    else:
        print("Insufficient USDT balance to place market order.")
        return {"error": "Insufficient USDT balance to place market order."}


def get_all_balances():
    params = {
        'timestamp': get_adjusted_timestamp()
    }
    params['signature'] = sign_request(params)
    url = f"{BASE_URL}/api/v3/account"
    try:
        response = requests.get(url, headers=headers(), params=params)
        response.raise_for_status()
        balances = response.json().get('balances', [])
        print(f"Fetched Balances: {balances}")  # Debugging
        return balances
    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch balances. Exception: {e}")
        if response:
            print("Response:", response.json())
        return []

def get_last_price(asset, base='USDT'):
    url = f"{BASE_URL}/api/v3/ticker/price"
    params = {'symbol': f"{asset}{base}"}
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        last_price = float(response.json()['price'])
        print(f"Last Price for {asset}: {last_price}")  # Debugging
        return last_price
    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch last price for {asset}. Exception: {e}")
        if response:
            print("Response:", response.json())
        return None

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.CYBORG])

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
        interval=5 * 1000,  # 10 seconds for debugging purposes
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
            try:
                if button_id == "buy-market-order-button":
                    response = place_market_order(symbol, quantity, 'BUY')
                elif button_id == "sell-market-order-button":
                    response = place_market_order(symbol, quantity, 'SELL')
                return f"Market Order Response: status: {response['status']}, side: {response['side']}, qty: {response['executedQty']}"
            except Exception as e:
                print(f"Error in handling market order: {e}")
                return f"Error: {e}"
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
            try:
                if button_id == "buy-limit-order-button":
                    response = place_limit_order(symbol, quantity, price, 'BUY')
                elif button_id == "sell-limit-order-button":
                    response = place_limit_order(symbol, quantity, price, 'SELL')
                # Debugging information
                print("Limit order response:", response)
                if response is None or 'error' in response:
                    return f"Error: Limit order could not be placed. {response.get('error', '')}"
                return f"Limit Order Response: status: {response.get('status')}, side: {response.get('side')}, qty: {response.get('origQty')}"
            except Exception as e:
                print(f"Error in handling limit order: {e}")
                return f"Error: {e}"
        return "Invalid PIN or no action taken."




@app.callback(
    Output('oco-output-container', 'children'),
    Input('oco-order-button', 'n_clicks'),
    State('oco-target-price-input', 'value'),
    State('oco-stop-price-input', 'value'),
    State('pin-input', 'value')
)
def handle_oco_order(n_clicks, target_price, stop_price, pin, symbol=None):
    if n_clicks > 0 and pin == PIN:
        try:
            response = oco_short_btcusdt(target_price, stop_price)
            print("OCO order response:", response)  # Debugging
            if response is None:
                return "Error: OCO order could not be placed."
            if 'error' in response:
                return f"Error: {response['error']}"
            # Print the entire response for debugging
            return f"OCO Order Response: {response}"
        except Exception as e:
            print(f"Error in handling OCO order: {e}")
            return f"Error: {e}"
    return "Invalid PIN or no action taken."



# Implement callback to update the table and pie chart with fetched balances
@app.callback(
    Output('balances-table', 'children'),
    Output('balances-pie-chart', 'figure'),
    Input('interval-component', 'n_intervals')
)
def update_balances_table_and_chart(n_intervals):
    print(f"Balances Callback triggered at interval: {n_intervals}")  # Debugging
    try:
        balances = get_all_balances()
        print("Balances:", balances) 
        if balances:
            balances = [balance for balance in balances if float(balance['free']) > 0]

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

            labels = [balance['asset'] for balance in balances]
            values = [float(balance['free']) for balance in balances]

            usdt_prices = {asset: get_last_price(asset) for asset in labels}
            print("Downloaded values for each coin:")
            for asset, price in usdt_prices.items():
                print(f"{asset}: {price}")

            for asset in labels:
                if asset not in usdt_prices:
                    usdt_prices[asset] = 1

            usdt_prices = {asset: price for asset, price in usdt_prices.items() if price is not None and asset != 'ETHW'}
            values_in_usdt = [value * usdt_prices[asset] for value, asset in zip(values, labels) if asset in usdt_prices]
            print("Pie Chart Labels:", labels)
            print("Pie Chart Values in USDT:", values_in_usdt)

            pie_chart = {
                'data': [
                    {'labels': labels, 'values': values_in_usdt, 'type': 'pie'}
                ],
                'layout': {
                    'title': 'Asset Balances'
                }
            }

            return table, pie_chart

    except Exception as e:
        print(f"Error in update_balances_table_and_chart: {e}")

    return dash.no_update, dash.no_update


if __name__ == '__main__':
    app.run_server(os.getenv("HOST", "0.0.0.0"), port=os.getenv("PORT", 8080))

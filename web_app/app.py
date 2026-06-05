import os
import json
import joblib
import pandas as pd
import numpy as np
import yfinance as yf
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder='static')

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_DIR = os.path.join(BASE_DIR, 'exported_model')

# Load models and config
config_path = os.path.join(MODEL_DIR, 'model_config.json')
with open(config_path, 'r') as f:
    config = json.load(f)

gbr_model = joblib.load(os.path.join(MODEL_DIR, 'best_gbr.joblib'))
xgb_model = joblib.load(os.path.join(MODEL_DIR, 'best_xgb.joblib'))

FEATURES = config['selected_features_final']
LOWER_THRESH = config['final_lower']
UPPER_THRESH = config['final_upper']
W_GBR = config['final_w_gbr']
W_XGB = config['final_w_xgb']
LABEL_MAP = {int(k): v for k, v in config['label_map'].items()}

# Auto-sync dataset
def load_and_sync_dataset(csv_path):
    df = pd.read_csv(csv_path)
    df['Date'] = pd.to_datetime(df['Date'])
    last_date = df['Date'].max()
    today = pd.to_datetime('today').normalize()
    
    if last_date < today:
        print(f"Updating dataset from {last_date.date()} to {today.date()}...")
        tickers = {
            'USDIDR': 'IDR=X', 'DXY': 'DX-Y.NYB', 'BRENT': 'BZ=F', 
            'GOLD': 'GC=F', 'VIX': '^VIX', 'IHSG': '^JKSE', 
            'US10Y': '^TNX', 'SP500': '^GSPC'
        }
        start_fetch = (last_date + pd.Timedelta(days=1)).strftime('%Y-%m-%d')
        end_fetch = (today + pd.Timedelta(days=1)).strftime('%Y-%m-%d')
        
        new_data = pd.DataFrame()
        for col, ticker in tickers.items():
            try:
                t_data = yf.download(ticker, start=start_fetch, end=end_fetch, progress=False)
                if not t_data.empty:
                    if isinstance(t_data.columns, pd.MultiIndex):
                        if 'Close' in t_data.columns.get_level_values(0):
                            series = t_data['Close'].iloc[:, 0]
                        else:
                            series = t_data.iloc[:, 0]
                    elif 'Close' in t_data.columns:
                        series = t_data['Close']
                    else:
                        series = t_data.iloc[:, 0]
                    new_data[col] = series
            except Exception as e:
                pass
                
        if not new_data.empty:
            new_data = new_data.reset_index()
            if 'index' in new_data.columns:
                new_data.rename(columns={'index': 'Date'}, inplace=True)
            new_data['Date'] = new_data['Date'].dt.tz_localize(None)
            
            if 'USDIDR' in new_data.columns:
                new_data = new_data.dropna(subset=['USDIDR'])
                
            if not new_data.empty:
                df_combined = pd.concat([df, new_data], ignore_index=True)
                df_combined.ffill(inplace=True)
                df_combined['Date'] = df_combined['Date'].dt.strftime('%Y-%m-%d')
                try:
                    df_combined.to_csv(csv_path, index=False)
                    print(f"Dataset updated with {len(new_data)} new rows.")
                except OSError:
                    print(f"Vercel Read-Only env: Dataset updated with {len(new_data)} new rows in memory only.")
                return df_combined
                
    df['Date'] = df['Date'].dt.strftime('%Y-%m-%d')
    return df

# Pre-load historical data for charts
try:
    csv_path = os.path.join(BASE_DIR, 'rupiah_dataset_fixed_auto.csv')
    df_history_full = load_and_sync_dataset(csv_path)
    df_history = df_history_full[['Date', 'USDIDR']].tail(365).copy()
    hist_dates = df_history['Date'].tolist()
    hist_prices = df_history['USDIDR'].tolist()
except Exception as e:
    hist_dates = []
    hist_prices = []
    print("Warning: Could not load historical data.", e)

def calculate_confidence(pred_return):
    # Pseudo-probability heuristic based on distance from thresholds
    # Returns (prob_menguat, prob_stabil, prob_melemah) in percentages
    if pred_return < LOWER_THRESH:
        dist = abs(pred_return - LOWER_THRESH)
        conf = min(99.0, 60.0 + (dist * 15.0))
        rem = 100.0 - conf
        return [round(conf, 1), round(rem * 0.8, 1), round(rem * 0.2, 1)]
    elif pred_return > UPPER_THRESH:
        dist = pred_return - UPPER_THRESH
        conf = min(99.0, 60.0 + (dist * 15.0))
        rem = 100.0 - conf
        return [round(rem * 0.2, 1), round(rem * 0.8, 1), round(conf, 1)]
    else:
        dist_from_edge = min(abs(pred_return - LOWER_THRESH), abs(pred_return - UPPER_THRESH))
        conf = min(95.0, 50.0 + (dist_from_edge * 40.0))
        rem = 100.0 - conf
        return [round(rem * 0.5, 1), round(conf, 1), round(rem * 0.5, 1)]

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/fetch_data', methods=['GET'])
def fetch_data():
    try:
        # Tickers according to ambildata.ipynb
        tickers = {
            'USDIDR': 'IDR=X',
            'DXY': 'DX-Y.NYB',
            'VIX': '^VIX',
            'IHSG': '^JKSE'
        }
        
        result = {}
        # Fetch latest 5 days to ensure we get the most recent valid close
        for key, ticker_symbol in tickers.items():
            data = yf.download(ticker_symbol, period='5d', auto_adjust=True, progress=False)
            if not data.empty:
                close_data = data['Close']
                if isinstance(close_data, pd.DataFrame):
                    val = close_data.iloc[-1, 0]
                else:
                    val = close_data.iloc[-1]
                
                if isinstance(val, pd.Series):
                    val = val.iloc[0]
                    
                result[key] = round(float(val), 2)
            else:
                result[key] = 0.0
                
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/predict', methods=['POST'])
def predict():
    try:
        data = request.json
        
        # Get user raw input data
        user_input = {k: float(v) for k, v in data.items() if v}
        
        # Calculate advanced features dynamically using historical data
        df_full = df_history_full.copy()
        
        # Create a new row for the "current day" with user's inputs overriding the last known values
        new_row = df_full.iloc[-1].copy()
        for col in ['USDIDR', 'DXY', 'VIX', 'IHSG', 'BI_Rate']:
            if col in user_input:
                new_row[col] = user_input[col]
        
        from datetime import datetime
        new_row['Date'] = datetime.today().strftime('%Y-%m-%d')
                
        df_full.loc[len(df_full)] = new_row
        
        # Calculate features using Pandas
        input_data = {}
        input_data['USDIDR'] = df_full['USDIDR'].iloc[-1]
        input_data['DXY'] = df_full['DXY'].iloc[-1]
        input_data['VIX'] = df_full['VIX'].iloc[-1]
        input_data['IHSG'] = df_full['IHSG'].iloc[-1]
        input_data['BI_Rate'] = df_full['BI_Rate'].iloc[-1]
        
        # Computed features mirroring the notebook
        input_data['USDIDR_roll_mean20'] = df_full['USDIDR'].rolling(20).mean().iloc[-1]
        input_data['M2_growth_12m'] = df_full['M2_ID'].pct_change(365).iloc[-1] * 100.0
        input_data['US10Y_roll_mean20'] = df_full['US10Y'].rolling(20).mean().iloc[-1]
        input_data['IHSG_roll_mean20'] = df_full['IHSG'].rolling(20).mean().iloc[-1]
        input_data['BRENT_return_1d'] = df_full['BRENT'].pct_change(1).iloc[-1] * 100.0
        input_data['IHSG_roll_std20'] = df_full['IHSG'].rolling(20).std().iloc[-1]
        input_data['high_vix_regime'] = 1.0 if df_full['VIX'].iloc[-1] >= 25.0 else 0.0
        input_data['rate_diff'] = df_full['BI_Rate'].iloc[-1] - df_full['FED_RATE'].iloc[-1]
        
        # Verify we have all required features and build ordered dict
        final_input = {}
        for feat in FEATURES:
            final_input[feat] = float(input_data.get(feat, 0.0))
            
        df = pd.DataFrame([final_input])
        
        # Predict using base models
        pred_gbr = gbr_model.predict(df)[0]
        pred_xgb = xgb_model.predict(df)[0]
        
        # Ensemble prediction (Weighted average)
        total_weight = W_GBR + W_XGB
        pred_return = ((pred_gbr * W_GBR) + (pred_xgb * W_XGB)) / total_weight
        
        # Classification logic
        if pred_return < LOWER_THRESH:
            pred_class = 0
        elif pred_return > UPPER_THRESH:
            pred_class = 2
        else:
            pred_class = 1
            
        pred_label = LABEL_MAP[pred_class]
        
        # Confidence Pseudo-probabilities
        probs = calculate_confidence(pred_return)
        
        # Estimate next price
        latest_price = input_data.get('USDIDR', 0)
        predicted_price = latest_price * (1 + pred_return / 100)
        
        # Feature Importance (Extract from XGBoost)
        importances = xgb_model.feature_importances_
        # Normalize to percentage
        importances = 100.0 * (importances / importances.sum())
        feat_imp_dict = {FEATURES[i]: round(float(importances[i]), 2) for i in range(len(FEATURES))}
        sorted_feats = sorted(feat_imp_dict.items(), key=lambda x: x[1], reverse=True)
        top_features = [{"feature": k, "importance": v} for k, v in sorted_feats[:6]]
        
        # Market Sentiment & Risk Logic
        vix = input_data.get('VIX', 15)
        dxy = input_data.get('DXY', 100)
        
        if vix > 25:
            risk_level = "Tinggi"
            risk_color = "red"
        elif vix > 18:
            risk_level = "Sedang"
            risk_color = "orange"
        else:
            risk_level = "Rendah"
            risk_color = "green"
            
        if pred_class == 0:
            sentiment = "Bullish (Rupiah Menguat)"
            trend_insight = "Model ensemble mendeteksi kondisi makroekonomi yang menguntungkan, kemungkinan didorong oleh kombinasi diferensial suku bunga dan risiko global yang lebih rendah, mengarah pada apresiasi Rupiah."
        elif pred_class == 2:
            sentiment = "Bearish (Rupiah Melemah)"
            trend_insight = f"Tekanan global yang kuat, kemungkinan diindikasikan oleh Indeks Dolar yang tinggi (DXY di level {dxy}) atau *capital outflow*, memberikan sinyal tren depresiasi untuk Rupiah dalam 30 hari ke depan."
        else:
            sentiment = "Netral / Sideways"
            trend_insight = "Kekuatan pasar tampak seimbang. Model memprediksi nilai tukar akan bergerak di sekitar level saat ini, tertahan kuat di dalam batas stabilitas."
            
        # Top driver insight
        top_driver = top_features[0]['feature']
        trend_insight += f" Faktor yang paling berpengaruh saat ini adalah '{top_driver}'."

        recent_df = df_full[['Date', 'USDIDR']].tail(365)
        current_hist_dates = recent_df['Date'].tolist()
        current_hist_prices = recent_df['USDIDR'].tolist()

        return jsonify({
            'success': True,
            'predicted_return_30d': round(pred_return, 4),
            'predicted_price_30d': round(predicted_price, 2),
            'predicted_class': pred_class,
            'predicted_label': pred_label,
            'latest_price': latest_price,
            'probabilities': {
                'menguat': probs[0],
                'stabil': probs[1],
                'melemah': probs[2]
            },
            'feature_importance': top_features,
            'historical_dates': current_hist_dates,
            'historical_prices': current_hist_prices,
            'market_sentiment': sentiment,
            'risk_level': risk_level,
            'risk_color': risk_color,
            'ai_insight': trend_insight
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 400

if __name__ == '__main__':
    app.run(debug=True, port=5000)

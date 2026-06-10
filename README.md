# Final-Project-VINIX7
Sistem prediksi kondisi nilai tukar Rupiah (USD/IDR) 30 hari ke depan menggunakan pendekatan **Regression-to-Classification (R2C)** dan model **Ensemble Gradient Boosting + XGBoost**.Model memprediksi return USD/IDR terlebih dahulu, kemudian mengonversinya menjadi tiga kategori kondisi pasar: Menguat, Stabil, atau Melemah menggunakan asymmetric threshold optimization

## Features

- Prediksi kondisi Rupiah: Menguat, Stabil, atau Melemah
- Simulasi perubahan indikator ekonomi
- Visualisasi tren dan proyeksi USD/IDR
- Explainable AI menggunakan SHAP

## Dataset

Periode data: **Juli 2007 – Mei 2026**

Variabel utama:

- USD/IDR
- DXY
- VIX
- FED Rate
- BI Rate
- IHSG
- Gold
- Brent Oil
- US10Y Treasury Yield
- FX Reserve
- Trade Balance

## Methodology

1. Data Cleaning
2. Feature Engineering
3. Regression-to-Classification (R2C)
4. Hyperparameter & Threshold Optimization
5. Ensemble Gradient Boosting + XGBoost
6. SHAP Explainability

## Result

| Model | Macro F1 |
|---------|---------|
| Gradient Boosting | 0.524 |
| Ensemble GBR + XGBoost | 0.567 |

Model ensemble menghasilkan performa terbaik dalam memprediksi kondisi Rupiah 30 hari ke depan.

## Run

```bash
pip install -r requirements.txt
python app.py
```

## Author
Aufatir Diaul Haq

# Robotics & Automation: Quant Equity Screener

## Overview
This Streamlit-based web application is a quantitative equity screener and risk-analysis dashboard. It evaluates a curated universe of robotics manufacturers and critical tier 1/tier 2 component suppliers (Hardware, AI compute, Machine Vision, and Automation). The tool bridges qualitative investment mandates (identifying companies with deep competitive moats) with quantitative risk metrics.

## Key Features
* **Live Fundamental Data Integration:** Utilizes `yfinance` to pull real-time pricing, P/E ratios, Beta, 52-week highs/lows, revenues, and earnings. 
* **Dynamic Currency Conversion:** Standardizes international fundamental metrics into a uniform currency style (e.g., 628 M€ or 1 B€) for seamless cross-border comparison.
* **Interactive Filtering:** Allows users to segment the equity universe geographically (USA, EU, Japan, China, South Korea, Canada).
* **Automated Risk Modeling:** Computes Historical Value at Risk (VaR) utilizing 3 years of daily adjusted closing prices.

## Quantitative Risk Methodology
The dashboard assumes a standardized investment volume of 1 M€ per equity to provide an apples-to-apples baseline for risk exposure. The risk module relies on a Historical Simulation approach scaled by the square root of time.

The 10-day Value at Risk at a 95% confidence interval is calculated as:
$$VaR_{10d, 95\%} = \text{Percentile}(R_{daily}, 0.05) \cdot \sqrt{10} \cdot 1,000,000$$

The 250-day Value at Risk at a 99% confidence interval is calculated as:
$$VaR_{250d, 99\%} = \text{Percentile}(R_{daily}, 0.01) \cdot \sqrt{250} \cdot 1,000,000$$

*(Note: $R_{daily}$ represents the array of daily percentage returns over the trailing 3-year period).*

## Architecture & Tech Stack
* **Frontend/Backend:** Python 3.10+, Streamlit
* **Data Ingestion:** `yfinance` (Yahoo Finance API)
* **Data Processing:** `pandas`, `numpy`
* **Performance:** Implements `@st.cache_data` to prevent API rate limiting and ensure snappy UI refreshes.

## Installation & Local Execution

1. **Clone the repository:**
   git clone https://github.com/your-org/robotics-quant-screener.git
   cd robotics-quant-screener

2. **Install dependencies:**
   pip install -r requirements.txt

3. **Run the Streamlit application:**
   streamlit run app.py

4. **Access the dashboard:**
   Open your browser and navigate to `http://localhost:8501`.

## Deployment
This application is designed to be easily deployed via [Streamlit Community Cloud](https://streamlit.io/cloud). Simply connect this GitHub repository to your Streamlit account, select `app.py` as the main file, and deploy.

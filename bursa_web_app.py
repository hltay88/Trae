import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from bursa_core import MARKET_INSIGHTS, get_stock_data, analyze_breakout, search_bursa, get_top_breakouts, KLCI_COMPONENTS

# --- PAGE CONFIG ---
st.set_page_config(page_title="Lawrence Tay's Research Project", layout="wide", page_icon="📈")

# --- UI ---
st.title("📈 Lawrence Tay's Research Project - Bursa Malaysia Breakout Analyzer")
st.markdown("---")

# Initialize session state for watchlist
if 'watchlist' not in st.session_state:
    with st.spinner("Initializing Market Discovery... scanning 30+ major stocks for breakouts."):
        # Get top 10 breakouts from KLCI components on first load
        top_breakouts = get_top_breakouts(limit=10)
        st.session_state.watchlist = [res['ticker'] for res in top_breakouts]

# Sidebar for adding stocks
st.sidebar.header("🔍 Search & Add Stock")
new_stock = st.sidebar.text_input("Enter Name, Code or Futures (e.g., GENTING, 0166, FKLI)")
if st.sidebar.button("Add to Dashboard"):
    ticker = search_bursa(new_stock)
    
    if ticker:
        if ticker not in st.session_state.watchlist:
            st.session_state.watchlist.append(ticker)
            st.success(f"Added {ticker}!")
            st.rerun()
        else:
            st.info(f"{ticker} is already in your list.")
    else:
        st.error("Could not find stock or future counter. Try using the exact code (e.g., 5347).")

if st.sidebar.button("🔄 Refresh Market Discovery"):
    with st.spinner("Re-scanning KLCI components for new breakouts..."):
        top_breakouts = get_top_breakouts(limit=10)
        st.session_state.watchlist = [res['ticker'] for res in top_breakouts]
        st.success("Dashboard updated with latest top 10 breakouts!")
        st.rerun()

if st.sidebar.button("🗑️ Clear Custom Stocks"):
    # Revert to top breakouts instead of a hardcoded list
    top_breakouts = get_top_breakouts(limit=10)
    st.session_state.watchlist = [res['ticker'] for res in top_breakouts]
    st.rerun()

# Main Dashboard Table
st.subheader("📊 Top 10 Dynamic Breakouts & Watchlist")
data_rows = []

# Use a spinner for the load
with st.spinner("Fetching latest live prices..."):
    for t in st.session_state.watchlist:
        df, name = get_stock_data(t, period="1y")
        
        if df is not None and not df.empty:
            analysis = analyze_breakout(t, df, name)
            if analysis:
                data_rows.append({
                    "Ticker": t,
                    "Name": analysis['name'],
                    "Price": analysis['price'],
                    "Score": f"{analysis['score']}/5",
                    "RSI": analysis['rsi'],
                    "Status": "🔥 BREAKOUT" if analysis['score'] >= 4 else "⚖️ Neutral",
                    "Analysis": analysis['analysis']
                })
        else:
            data_rows.append({
                "Ticker": t,
                "Name": "Loading Error",
                "Price": 0.0,
                "Score": "N/A",
                "RSI": 0.0,
                "Status": "❌ No Data",
                "Analysis": "Could not fetch live data from Yahoo Finance."
            })

if data_rows:
    df_display = pd.DataFrame(data_rows)
    st.dataframe(df_display, use_container_width=True, hide_index=True)
else:
    st.warning("No data found. Please click 'Refresh Market Discovery' or add valid tickers.")

# Detailed Chart Section
st.markdown("---")
st.subheader("🕯️ Interactive Candlestick Chart")

if st.session_state.watchlist:
    selected_stock = st.selectbox("Select stock or future to view chart", st.session_state.watchlist)

    if selected_stock:
        with st.spinner(f"Loading chart for {selected_stock}..."):
            df_chart, name_chart = get_stock_data(selected_stock, period="5y")
            
            if df_chart is None or df_chart.empty:
                st.warning(f"5-year data unavailable for {selected_stock}. Trying 1-year data...")
                df_chart, name_chart = get_stock_data(selected_stock, period="1y")

            if df_chart is not None and not df_chart.empty:
                # Indicators
                df_chart['SMA20'] = df_chart['Close'].rolling(window=20).mean()
                df_chart['SMA50'] = df_chart['Close'].rolling(window=50).mean()
                
                # Show last 100 days for candlestick
                plot_df = df_chart.tail(100)
                
                if not plot_df.empty:
                    fig = go.Figure()
                    fig.add_trace(go.Candlestick(x=plot_df.index,
                            open=plot_df['Open'], high=plot_df['High'],
                            low=plot_df['Low'], close=plot_df['Close'], name='Market'))
                    
                    if 'SMA20' in plot_df.columns:
                        fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['SMA20'], line=dict(color='orange', width=1.5), name='SMA 20'))
                    if 'SMA50' in plot_df.columns:
                        fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['SMA50'], line=dict(color='blue', width=1.5), name='SMA 50'))
                    
                    fig.update_layout(title=f"{name_chart} ({selected_stock}) - Price Action", 
                                      yaxis_title="Price",
                                      xaxis_rangeslider_visible=False,
                                      template="plotly_white",
                                      height=600)
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    vol_colors = ['green' if plot_df['Close'].iloc[i] >= plot_df['Open'].iloc[i] else 'red' for i in range(len(plot_df))]
                    vol_fig = go.Figure(go.Bar(x=plot_df.index, y=plot_df['Volume'], name='Volume', marker_color=vol_colors))
                    vol_fig.update_layout(title="Trading Volume", height=300, template="plotly_white")
                    st.plotly_chart(vol_fig, use_container_width=True)
                else:
                    st.error("Historical price data is too short for charting.")
            else:
                st.error(f"Could not load any historical data for {selected_stock}.")
else:
    st.info("Add some stocks or futures from the sidebar to see charts.")

st.sidebar.markdown("---")
show_debug = st.sidebar.checkbox("Show Debug Info")
if show_debug:
    st.sidebar.write("Current Watchlist:", st.session_state.watchlist)

st.sidebar.info("Market Discovery scans 30 major KLCI stocks every time the dashboard is initialized or refreshed.")

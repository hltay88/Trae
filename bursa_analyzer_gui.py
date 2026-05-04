import datetime
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
from bursa_core import MARKET_INSIGHTS, get_stock_data, analyze_breakout, search_bursa, get_top_breakouts, KLCI_COMPONENTS, get_futures_breakouts

class BursaAnalyzerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Bursa Malaysia Breakout Analyzer (Dynamic)")
        self.root.geometry("1100x650")
        self.root.configure(bg="#f0f2f5")

        self.style = ttk.Style()
        self.style.theme_use("clam")
        
        # Header
        self.header_frame = tk.Frame(self.root, bg="#1a237e", height=80)
        self.header_frame.pack(fill="x")
        
        self.title_label = tk.Label(self.header_frame, text="BURSA MALAYSIA DYNAMIC BREAKOUT ANALYZER", 
                                    font=("Helvetica", 18, "bold"), fg="white", bg="#1a237e")
        self.title_label.pack(pady=20)

        # Control Frame
        self.control_frame = tk.Frame(self.root, bg="#f0f2f5", pady=10)
        self.control_frame.pack(fill="x", padx=20)

        self.scan_btn = tk.Button(self.control_frame, text="REFRESH TOP 10", command=self.start_scan,
                                  font=("Helvetica", 10, "bold"), bg="#4caf50", fg="white", 
                                  padx=15, pady=5, relief="flat", cursor="hand2")
        self.scan_btn.pack(side="left")

        # Add Search Bar
        tk.Label(self.control_frame, text="Stock Name / Code:", font=("Helvetica", 10, "bold"), bg="#f0f2f5").pack(side="left", padx=(20, 5))
        self.search_entry = tk.Entry(self.control_frame, font=("Helvetica", 10), width=20)
        self.search_entry.pack(side="left", padx=5)
        self.search_entry.insert(0, "INARI") 
        
        self.add_btn = tk.Button(self.control_frame, text="SEARCH & ADD", command=self.add_custom_stock,
                                 font=("Helvetica", 10, "bold"), bg="#2196f3", fg="white", 
                                 padx=15, pady=5, relief="flat", cursor="hand2")
        self.add_btn.pack(side="left", padx=5)

        self.status_label = tk.Label(self.control_frame, text="Ready to scan...", font=("Helvetica", 10), bg="#f0f2f5")
        self.status_label.pack(side="left", padx=20)

        # Keep track of custom tickers
        self.custom_tickers = []

        # Notebook for Tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=20, pady=10)

        # Table Frame (Stocks)
        self.table_frame = tk.Frame(self.notebook, bg="white")
        self.notebook.add(self.table_frame, text="  📊 STOCKS  ")

        columns = ("code", "name", "price", "score", "rsi", "analysis", "catalyst")
        self.tree = ttk.Treeview(self.table_frame, columns=columns, show="headings")
        
        # Define Headings
        self.tree.heading("code", text="Code")
        self.tree.heading("name", text="Name")
        self.tree.heading("price", text="Price (RM)")
        self.tree.heading("score", text="Breakout Score")
        self.tree.heading("rsi", text="RSI")
        self.tree.heading("analysis", text="Deep Analysis")
        self.tree.heading("catalyst", text="Key Catalyst")

        # Define Columns
        self.tree.column("code", width=60, anchor="center")
        self.tree.column("name", width=120, anchor="center")
        self.tree.column("price", width=80, anchor="center")
        self.tree.column("score", width=100, anchor="center")
        self.tree.column("rsi", width=60, anchor="center")
        self.tree.column("analysis", width=350)
        self.tree.column("catalyst", width=250)

        # Scrollbar
        self.scrollbar = ttk.Scrollbar(self.table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=self.scrollbar.set)
        
        self.tree.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
        # Futures Frame
        self.futures_frame = tk.Frame(self.notebook, bg="white")
        self.notebook.add(self.futures_frame, text="  ⛓️ FUTURES  ")

        self.futures_tree = ttk.Treeview(self.futures_frame, columns=columns, show="headings")
        for col in columns:
            self.futures_tree.heading(col, text=self.tree.heading(col)["text"])
            self.futures_tree.column(col, width=self.tree.column(col)["width"], anchor=self.tree.column(col)["anchor"])
        
        self.f_scrollbar = ttk.Scrollbar(self.futures_frame, orient="vertical", command=self.futures_tree.yview)
        self.futures_tree.configure(yscrollcommand=self.f_scrollbar.set)
        self.futures_tree.pack(side="left", fill="both", expand=True)
        self.f_scrollbar.pack(side="right", fill="y")

        # Bind double-click to show chart
        self.tree.bind("<Double-1>", self.on_stock_double_click)
        self.futures_tree.bind("<Double-1>", self.on_stock_double_click)

        # Color Tags for Scores
        for t in [self.tree, self.futures_tree]:
            t.tag_configure("high_score", background="#e8f5e9", foreground="#2e7d32") # Green
            t.tag_configure("mid_score", background="#fffde7", foreground="#fbc02d")  # Yellow
            t.tag_configure("low_score", background="#ffebee", foreground="#c62828")  # Red

        # Initial scan
        self.start_scan()

    def on_stock_double_click(self, event):
        # Determine which tree was clicked
        tree = event.widget
        selection = tree.selection()
        if not selection: return
        
        item = selection[0]
        values = tree.item(item, "values")
        code = values[0]
        name = values[1]
        
        # We need to find the ticker from the watchlist or custom tickers
        ticker = f"{code}.KL"
        if code == "FKLI": ticker = "FKLI=F"
        elif code == "FCPO": ticker = "FCPO=F"
        elif code == "FM70": ticker = "FM70=F"
        
        # Show loading message
        self.status_label.config(text=f"Generating chart for {name}...")
        
        threading.Thread(target=self.show_chart_window, args=(ticker, name), daemon=True).start()

    def show_chart_window(self, ticker, name):
        try:
            # Using get_stock_data from bursa_core which has the fix
            df, resolved_name = get_stock_data(ticker, period="5y")
            if df is None or df.empty:
                # Try 1y if 5y fails
                df, resolved_name = get_stock_data(ticker, period="1y")
                
            if df is None or df.empty:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Could not fetch chart data for {ticker}."))
                return

            # Create popup window
            self.root.after(0, lambda: self._create_popup(df, name, ticker))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Chart Error: {str(e)}"))

    def _create_popup(self, df, name, ticker):
        popup = tk.Toplevel(self.root)
        popup.title(f"Live Candlestick Chart - {name} ({ticker})")
        popup.geometry("1000x800")
        
        # Header Info
        current_price = df['Close'].iloc[-1]
        change = current_price - df['Close'].iloc[-2]
        percent_change = (change / df['Close'].iloc[-2]) * 100
        color = "green" if change >= 0 else "red"
        
        info_frame = tk.Frame(popup, bg="white", pady=10)
        info_frame.pack(fill="x")
        
        tk.Label(info_frame, text=f"{name} ({ticker})", font=("Helvetica", 16, "bold"), bg="white").pack(side="left", padx=20)
        tk.Label(info_frame, text=f"RM {current_price:.3f}", font=("Helvetica", 16, "bold"), bg="white", fg=color).pack(side="left", padx=10)
        tk.Label(info_frame, text=f"{change:+.3f} ({percent_change:+.2f}%)", font=("Helvetica", 12), bg="white", fg=color).pack(side="left")

        # Plotting
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), gridspec_kw={'height_ratios': [3, 1]}, sharex=True)
        fig.patch.set_facecolor('#f0f2f5')

        # Calculate Candlestick parameters
        # For a 5-year chart, we use a wider width for candles or switch to line for clarity
        # However, user specifically asked for Candlesticks. To make it readable for 5 years,
        # we will show the last 6 months as candlesticks by default, but allow full 5y view.
        
        # Default to showing last 100 days for clear candlesticks, but data has 5 years
        plot_df = df.tail(100).copy() if len(df) > 100 else df.copy()
        
        # Custom Candlestick implementation using Matplotlib
        width = 0.6
        
        up = plot_df[plot_df.Close >= plot_df.Open]
        down = plot_df[plot_df.Close < plot_df.Open]
        
        # Re-draw properly
        if not up.empty:
            ax1.bar(up.index, up.Close - up.Open, width, bottom=up.Open, color='#26a69a', label='Up')
            ax1.vlines(up.index, up.Low, up.High, color='#26a69a', linewidth=1)
        
        if not down.empty:
            ax1.bar(down.index, down.Open - down.Close, width, bottom=down.Close, color='#ef5350', label='Down')
            ax1.vlines(down.index, down.Low, down.High, color='#ef5350', linewidth=1)
        
        # Moving Averages on full data
        df['SMA20'] = df['Close'].rolling(window=20).mean()
        df['SMA50'] = df['Close'].rolling(window=50).mean()
        
        # Plot MAs only for the visible range
        ax1.plot(plot_df.index, df['SMA20'].reindex(plot_df.index), color='#ff9800', linestyle='-', alpha=0.8, label='SMA 20')
        ax1.plot(plot_df.index, df['SMA50'].reindex(plot_df.index), color='#2196f3', linestyle='-', alpha=0.8, label='SMA 50')
        
        ax1.set_title(f"Daily Candlestick Chart (Latest 100 Days of 5-Year History)", fontsize=12, fontweight='bold')
        ax1.set_ylabel("Price (RM)")
        ax1.grid(True, linestyle=':', alpha=0.4)
        ax1.legend(loc='upper left')

        # Volume Chart
        vol_colors = ['#26a69a' if df['Close'].iloc[i] >= df['Open'].iloc[i] else '#ef5350' for i in range(len(df))]
        # Match volume colors to plot_df
        plot_vol_colors = [vol_colors[i] for i in range(len(df)) if df.index[i] in plot_df.index]
        
        ax2.bar(plot_df.index, plot_df['Volume'], color=plot_vol_colors, alpha=0.6)
        ax2.set_title("Trading Volume", fontsize=10, fontweight='bold')
        ax2.set_ylabel("Volume")
        ax2.grid(True, linestyle=':', alpha=0.4)
        
        # Formatting dates
        ax2.xaxis.set_major_formatter(mdates.DateFormatter('%d %b'))
        ax2.xaxis.set_major_locator(mdates.DayLocator(interval=15))
        fig.autofmt_xdate()

        canvas = FigureCanvasTkAgg(fig, master=popup)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)
        
        # Add a note about the 5-year data
        tk.Label(popup, text="* Chart shows latest 100 days for clarity. Full 5-year data used for technical calculations.", 
                 font=("Helvetica", 9, "italic"), bg="#f0f2f5").pack(pady=5)
        
        self.status_label.config(text="Ready")

    def add_custom_stock(self):
        user_input = self.search_entry.get().strip()
        if not user_input: return
        
        self.status_label.config(text=f"Searching for '{user_input}'...")
        self.add_btn.config(state="disabled")
        
        def search_thread():
            ticker = search_bursa(user_input)
            
            if ticker:
                if ticker not in self.custom_tickers and ticker not in MARKET_INSIGHTS:
                    self.custom_tickers.append(ticker)
                    self.root.after(0, self.start_scan)
                else:
                    self.root.after(0, lambda: messagebox.showinfo("Info", "This stock is already being tracked!"))
            else:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Could not find a Bursa stock matching '{user_input}'"))
            
            self.root.after(0, lambda: self.add_btn.config(state="normal"))

        threading.Thread(target=search_thread, daemon=True).start()

    def start_scan(self):
        self.scan_btn.config(state="disabled")
        self.add_btn.config(state="disabled")
        self.status_label.config(text="Fetching live Bursa data... please wait.")
        for item in self.tree.get_children(): self.tree.delete(item)
        for item in self.futures_tree.get_children(): self.futures_tree.delete(item)
        threading.Thread(target=self.run_analysis, daemon=True).start()

    def run_analysis(self):
        # 1. Scan Stocks
        self.status_label.config(text="Scanning 30+ stocks for top breakouts...")
        top_results = get_top_breakouts(limit=10)
        
        # Add custom tickers to the results as well
        for ticker in self.custom_tickers:
            df, resolved_name = get_stock_data(ticker)
            res = analyze_breakout(ticker, df, resolved_name)
            if res:
                if not any(r['ticker'] == ticker for r in top_results):
                    top_results.append(res)
        
        # Insert into stocks tree
        for res in top_results:
            tag = "low_score"
            if res['score'] >= 4: tag = "high_score"
            elif res['score'] >= 2: tag = "mid_score"
            
            self.tree.insert("", "end", values=(
                res['code'], res['name'], res['price'], 
                f"{res['score']} / 5", res['rsi'], res['analysis'], res['catalyst']
            ), tags=(tag,))

        # 2. Scan Futures
        self.status_label.config(text="Analyzing Malaysian Futures market...")
        futures_results = get_futures_breakouts()
        
        for res in futures_results:
            tag = "low_score"
            if res['score'] >= 4: tag = "high_score"
            elif res['score'] >= 2: tag = "mid_score"
            
            self.futures_tree.insert("", "end", values=(
                res['code'], res['name'], res['price'], 
                f"{res['score']} / 5", res['rsi'], res['analysis'], res['catalyst']
            ), tags=(tag,))
        
        self.root.after(0, self.finish_scan)

    def finish_scan(self):
        self.scan_btn.config(state="normal")
        self.add_btn.config(state="normal")
        self.status_label.config(text=f"Last updated: {datetime.datetime.now().strftime('%H:%M:%S')}")

if __name__ == "__main__":
    root = tk.Tk()
    app = BursaAnalyzerGUI(root)
    root.mainloop()

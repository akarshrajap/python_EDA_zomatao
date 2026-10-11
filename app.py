import os
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from collections import Counter

# Set page configuration
st.set_page_config(
    page_title="Zomato Bangalore Data Telemetry Dashboard",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling (Modern Dark Glassmorphism Design System)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    /* Global App Background */
    .stApp {
        background: linear-gradient(135deg, #0b0f19 0%, #111827 50%, #0d1322 100%);
        color: #f3f4f6;
    }
    
    /* Header Card */
    .header-box {
        background: rgba(17, 24, 39, 0.7);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 24px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
    }
    
    .header-title {
        font-size: 2.2rem;
        font-weight: 700;
        background: linear-gradient(90deg, #ff4b4b 0%, #ff7676 50%, #ffa07a 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
        padding: 0;
    }
    
    .header-sub {
        color: #9ca3af;
        font-size: 0.95rem;
        margin-top: 6px;
    }
    
    /* Metric Cards */
    .metric-card {
        background: rgba(31, 41, 55, 0.6);
        backdrop-filter: blur(8px);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 12px;
        padding: 18px 20px;
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        border-color: rgba(255, 75, 75, 0.4);
    }
    
    .metric-label {
        font-size: 0.82rem;
        font-weight: 500;
        color: #9ca3af;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    .metric-val {
        font-size: 1.85rem;
        font-weight: 700;
        color: #f9fafb;
        margin: 4px 0;
    }
    
    .metric-badge {
        display: inline-block;
        font-size: 0.75rem;
        padding: 3px 8px;
        border-radius: 9999px;
        font-weight: 600;
    }
    .badge-green { background: rgba(16, 185, 129, 0.15); color: #34d399; }
    .badge-blue { background: rgba(59, 130, 246, 0.15); color: #60a5fa; }
    .badge-purple { background: rgba(168, 85, 247, 0.15); color: #c084fc; }
    .badge-red { background: rgba(239, 68, 68, 0.15); color: #f87171; }
    
    /* Tabs styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: transparent;
    }
    
    .stTabs [data-baseweb="tab"] {
        background: rgba(31, 41, 55, 0.5);
        border-radius: 8px;
        padding: 8px 18px;
        color: #9ca3af;
        border: 1px solid rgba(255, 255, 255, 0.05);
    }
    
    .stTabs [aria-selected="true"] {
        background: rgba(255, 75, 75, 0.15) !important;
        color: #ff4b4b !important;
        border-color: rgba(255, 75, 75, 0.4) !important;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# Data Ingestion & Caching Layer
# -------------------------------------------------------------
@st.cache_data(show_spinner="Ingesting Restaurant Telemetry Stream...")
def load_data():
    primary_path = os.getenv("DATA_PATH", os.path.join("data", "telemetry_data.csv"))
    fallback_path = "zomato.csv"
    
    df = None
    if os.path.exists(primary_path):
        df = pd.read_csv(primary_path)
    elif os.path.exists(fallback_path):
        cols = ['name', 'online_order', 'book_table', 'rate', 'votes', 'location', 
                'rest_type', 'dish_liked', 'cuisines', 'approx_cost(for two people)', 
                'listed_in(type)', 'listed_in(city)']
        raw_df = pd.read_csv(fallback_path, usecols=cols)
        
        def clean_rate(val):
            if pd.isna(val): return None
            val_str = str(val).split('/')[0].strip()
            try: return float(val_str)
            except: return None

        def clean_cost(val):
            if pd.isna(val): return None
            try: return float(str(val).replace(',', '').strip())
            except: return None

        raw_df['rating'] = raw_df['rate'].apply(clean_rate)
        raw_df['cost_for_two'] = raw_df['approx_cost(for two people)'].apply(clean_cost)
        raw_df = raw_df.rename(columns={'listed_in(type)': 'service_type', 'listed_in(city)': 'city_zone'})
        df = raw_df.drop(columns=['rate', 'approx_cost(for two people)'])
    
    if df is not None:
        # Standardize strings & fill missing categories
        df['online_order'] = df['online_order'].fillna('No').astype(str).str.capitalize()
        df['book_table'] = df['book_table'].fillna('No').astype(str).str.capitalize()
        df['city_zone'] = df['city_zone'].fillna('Bangalore General').astype(str)
        df['location'] = df['location'].fillna('Unknown').astype(str)
        df['service_type'] = df['service_type'].fillna('Other').astype(str)
        df['votes'] = pd.to_numeric(df['votes'], errors='coerce').fillna(0).astype(int)
        
        # Categorize cost tiers
        def categorize_tier(cost):
            if pd.isna(cost): return "Unspecified"
            if cost < 400: return "Budget (< ₹400)"
            elif cost <= 800: return "Casual Dining (₹400-₹800)"
            elif cost <= 1500: return "Mid-Range (₹800-₹1500)"
            else: return "Fine Dining (> ₹1500)"
            
        df['cost_tier'] = df['cost_for_two'].apply(categorize_tier)
    return df

df_raw = load_data()

# -------------------------------------------------------------
# Sidebar & Filters
# -------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🎛️ Telemetry Telecontrol")
    st.markdown("<p style='color: #9ca3af; font-size: 0.85rem;'>Filter live restaurant telemetry signals</p>", unsafe_allow_html=True)

    if df_raw is None:
        st.error("No telemetry data source detected.")
        st.stop()

    # City Zone Filter
    all_zones = sorted(df_raw['city_zone'].dropna().unique().tolist())
    selected_zones = st.multiselect("📍 Urban Sector / Zone", all_zones, default=all_zones[:5])
    if not selected_zones:
        selected_zones = all_zones

    # Service Type Filter
    all_types = sorted(df_raw['service_type'].dropna().unique().tolist())
    selected_types = st.multiselect("🍽️ Service Category", all_types, default=all_types)
    if not selected_types:
        selected_types = all_types

    # Online Order & Table Booking
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        online_filter = st.selectbox("🛵 Online Order", ["All", "Yes", "No"])
    with col_f2:
        booking_filter = st.selectbox("📅 Table Booking", ["All", "Yes", "No"])

    # Rating Slider
    min_rating = float(df_raw['rating'].min(skipna=True) or 1.0)
    max_rating = float(df_raw['rating'].max(skipna=True) or 5.0)
    rating_range = st.slider("⭐ Rating Interval", min_value=1.0, max_value=5.0, value=(2.5, 5.0), step=0.1)

    # Cost Slider
    valid_costs = df_raw['cost_for_two'].dropna()
    min_cost = int(valid_costs.min()) if len(valid_costs) > 0 else 50
    max_cost = int(valid_costs.max()) if len(valid_costs) > 0 else 5000
    cost_range = st.slider("💰 Cost for Two (INR)", min_value=min_cost, max_value=max_cost, value=(min_cost, min(2500, max_cost)), step=50)

    # Cuisine search
    cuisine_search = st.text_input("🔍 Search Cuisine (e.g. Biryani, Italian)", "")

    st.markdown("---")
    st.markdown("""
        <div style='font-size:0.75rem; color:#6b7280; line-height:1.4;'>
            <b>Data Telemetry Dashboard v1.0</b><br/>
            Engine: Streamlit + Kubernetes<br/>
            Status: <span style='color:#10b981'>● Live Telemetry Active</span>
        </div>
    """, unsafe_allow_html=True)

# -------------------------------------------------------------
# Data Filtering
# -------------------------------------------------------------
filtered_df = df_raw[
    (df_raw['city_zone'].isin(selected_zones)) &
    (df_raw['service_type'].isin(selected_types))
]

if online_filter != "All":
    filtered_df = filtered_df[filtered_df['online_order'] == online_filter]

if booking_filter != "All":
    filtered_df = filtered_df[filtered_df['book_table'] == booking_filter]

# Rating filter
filtered_df = filtered_df[
    (filtered_df['rating'].isna()) | 
    ((filtered_df['rating'] >= rating_range[0]) & (filtered_df['rating'] <= rating_range[1]))
]

# Cost filter
filtered_df = filtered_df[
    (filtered_df['cost_for_two'].isna()) | 
    ((filtered_df['cost_for_two'] >= cost_range[0]) & (filtered_df['cost_for_two'] <= cost_range[1]))
]

# Cuisine search filter
if cuisine_search.strip():
    search_term = cuisine_search.strip().lower()
    filtered_df = filtered_df[
        filtered_df['cuisines'].fillna('').str.lower().str.contains(search_term)
    ]

# -------------------------------------------------------------
# Dashboard Header
# -------------------------------------------------------------
st.markdown("""
<div class="header-box">
    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">
        <div>
            <h1 class="header-title">Zomato Bangalore Data Telemetry</h1>
            <p class="header-sub">Real-time exploratory data analytics, dining behavior metrics & urban telemetry</p>
        </div>
        <div style="text-align:right;">
            <span class="metric-badge badge-green">🚀 Telemetry Streaming Active</span>
            <span class="metric-badge badge-blue">K8s Ready</span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# Top KPI Metric Strip
# -------------------------------------------------------------
total_monitored = len(filtered_df)
avg_rating = filtered_df['rating'].mean()
avg_cost = filtered_df['cost_for_two'].median()
online_order_pct = (filtered_df['online_order'] == 'Yes').mean() * 100 if total_monitored > 0 else 0
booking_pct = (filtered_df['book_table'] == 'Yes').mean() * 100 if total_monitored > 0 else 0
total_votes = filtered_df['votes'].sum()

m1, m2, m3, m4, m5, m6 = st.columns(6)

with m1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Nodes Monitored</div>
        <div class="metric-val">{total_monitored:,}</div>
        <span class="metric-badge badge-blue">Restaurants</span>
    </div>
    """, unsafe_allow_html=True)

with m2:
    rating_display = f"{avg_rating:.2f} ⭐" if not np.isnan(avg_rating) else "N/A"
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Avg Rating</div>
        <div class="metric-val">{rating_display}</div>
        <span class="metric-badge badge-green">Satisfaction</span>
    </div>
    """, unsafe_allow_html=True)

with m3:
    cost_display = f"₹{avg_cost:.0f}" if not np.isnan(avg_cost) else "N/A"
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Median Cost</div>
        <div class="metric-val">{cost_display}</div>
        <span class="metric-badge badge-purple">For Two Diners</span>
    </div>
    """, unsafe_allow_html=True)

with m4:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Online Delivery</div>
        <div class="metric-val">{online_order_pct:.1f}%</div>
        <span class="metric-badge badge-green">Fleet Enabled</span>
    </div>
    """, unsafe_allow_html=True)

with m5:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Table Booking</div>
        <div class="metric-val">{booking_pct:.1f}%</div>
        <span class="metric-badge badge-blue">Reservation Rate</span>
    </div>
    """, unsafe_allow_html=True)

with m6:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Customer Votes</div>
        <div class="metric-val">{total_votes:,}</div>
        <span class="metric-badge badge-purple">Total Feedback</span>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br/>", unsafe_allow_html=True)

# -------------------------------------------------------------
# Main Visual Tabs
# -------------------------------------------------------------
tab_overview, tab_geo, tab_cuisine, tab_operations, tab_data = st.tabs([
    "📊 Telemetry & Ratings",
    "🗺️ Geospatial & Zones",
    "🍲 Cuisine Telemetry",
    "⚡ Operational Analytics",
    "📋 Data Explorer & Export"
])

# Plotly theme styling template
chart_template = "plotly_dark"

# -------------------------------------------------------------
# TAB 1: Telemetry & Ratings
# -------------------------------------------------------------
with tab_overview:
    col_c1, col_c2 = st.columns(2)
    
    with col_c1:
        st.subheader("⭐ Rating Telemetry Distribution")
        valid_ratings = filtered_df['rating'].dropna()
        if len(valid_ratings) > 0:
            fig_hist = px.histogram(
                valid_ratings,
                x="rating",
                nbins=25,
                color_discrete_sequence=['#ff4b4b'],
                template=chart_template,
                title="Density of Restaurant Ratings (1.0 - 5.0)",
                labels={'rating': 'Rating score'}
            )
            fig_hist.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=20, r=20, t=40, b=20),
                bargap=0.1
            )
            st.plotly_chart(fig_hist, use_container_width=True)
        else:
            st.info("No rating data available for selected criteria.")

    with col_c2:
        st.subheader("💵 Cost vs Rating Scatter Telemetry")
        scatter_sample = filtered_df.dropna(subset=['rating', 'cost_for_two'])
        if len(scatter_sample) > 3000:
            scatter_sample = scatter_sample.sample(3000, random_state=42)
            
        if len(scatter_sample) > 0:
            fig_scatter = px.scatter(
                scatter_sample,
                x="cost_for_two",
                y="rating",
                color="online_order",
                size="votes",
                hover_name="name",
                hover_data=["location", "service_type"],
                color_discrete_map={"Yes": "#10b981", "No": "#ef4444"},
                template=chart_template,
                title="Cost for Two vs Rating (Bubble size = Votes)",
                labels={"cost_for_two": "Approx Cost for Two (INR)", "rating": "Rating", "online_order": "Online Order"}
            )
            fig_scatter.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=20, r=20, t=40, b=20)
            )
            st.plotly_chart(fig_scatter, use_container_width=True)
        else:
            st.info("Insufficient data for cost vs rating analysis.")

    # Top Rated & Most Popular Restaurants
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        st.subheader("🏆 Top Rated Outlets (Min 100 Votes)")
        qualified = filtered_df[filtered_df['votes'] >= 100].sort_values(by=['rating', 'votes'], ascending=False).drop_duplicates(subset=['name'])
        if len(qualified) > 0:
            top_rated_bar = px.bar(
                qualified.head(10),
                x="rating",
                y="name",
                orientation='h',
                color="rating",
                color_continuous_scale="Viridis",
                template=chart_template,
                hover_data=["cost_for_two", "location", "cuisines"],
                labels={"name": "Restaurant", "rating": "Rating Score"}
            )
            top_rated_bar.update_layout(
                yaxis=dict(autorange="reversed"),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=20, r=20, t=40, b=20)
            )
            st.plotly_chart(top_rated_bar, use_container_width=True)
        else:
            st.info("No restaurants matched the 100+ votes threshold.")

    with col_t2:
        st.subheader("🔥 Most Voted Restaurants (Highest Footfall)")
        most_voted = filtered_df.sort_values(by="votes", ascending=False).drop_duplicates(subset=['name']).head(10)
        if len(most_voted) > 0:
            voted_bar = px.bar(
                most_voted,
                x="votes",
                y="name",
                orientation='h',
                color="votes",
                color_continuous_scale="Reds",
                template=chart_template,
                hover_data=["rating", "cost_for_two", "location"],
                labels={"name": "Restaurant", "votes": "Total Customer Votes"}
            )
            voted_bar.update_layout(
                yaxis=dict(autorange="reversed"),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=20, r=20, t=40, b=20)
            )
            st.plotly_chart(voted_bar, use_container_width=True)

# -------------------------------------------------------------
# TAB 2: Geospatial & Zones
# -------------------------------------------------------------
with tab_geo:
    col_g1, col_g2 = st.columns(2)
    
    with col_g1:
        st.subheader("🏙️ Top Locations by Restaurant Concentration")
        loc_counts = filtered_df['location'].value_counts().head(15).reset_index()
        loc_counts.columns = ['location', 'count']
        
        fig_loc = px.bar(
            loc_counts,
            x="count",
            y="location",
            orientation='h',
            color="count",
            color_continuous_scale="Teal",
            template=chart_template,
            labels={"location": "Neighborhood", "count": "Active Outlets"}
        )
        fig_loc.update_layout(
            yaxis=dict(autorange="reversed"),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=20, r=20, t=40, b=20)
        )
        st.plotly_chart(fig_loc, use_container_width=True)

    with col_g2:
        st.subheader("💎 Average Dining Cost by Locality")
        loc_avg_cost = filtered_df.groupby('location')['cost_for_two'].agg(['mean', 'count']).reset_index()
        loc_avg_cost = loc_avg_cost[loc_avg_cost['count'] >= 50].sort_values(by='mean', ascending=False).head(15)
        
        fig_cost_loc = px.bar(
            loc_avg_cost,
            x="mean",
            y="location",
            orientation='h',
            color="mean",
            color_continuous_scale="Plasma",
            template=chart_template,
            labels={"location": "Neighborhood", "mean": "Average Cost for Two (INR)"}
        )
        fig_cost_loc.update_layout(
            yaxis=dict(autorange="reversed"),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=20, r=20, t=40, b=20)
        )
        st.plotly_chart(fig_cost_loc, use_container_width=True)

    st.subheader("🌐 Urban Zone Telemetry Comparison (City Hubs)")
    zone_agg = filtered_df.groupby('city_zone').agg(
        restaurants=('name', 'count'),
        avg_rating=('rating', 'mean'),
        median_cost=('cost_for_two', 'median'),
        online_rate=('online_order', lambda x: (x == 'Yes').mean() * 100)
    ).reset_index()
    
    fig_zone_bubble = px.scatter(
        zone_agg,
        x="median_cost",
        y="avg_rating",
        size="restaurants",
        color="online_rate",
        hover_name="city_zone",
        color_continuous_scale="Turbo",
        template=chart_template,
        title="Urban Zones: Median Cost vs Rating (Size: Density, Color: Delivery %)",
        labels={
            "median_cost": "Median Cost for Two (INR)",
            "avg_rating": "Average Rating",
            "online_rate": "Online Order %"
        }
    )
    fig_zone_bubble.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=40, b=20)
    )
    st.plotly_chart(fig_zone_bubble, use_container_width=True)

# -------------------------------------------------------------
# TAB 3: Cuisine Telemetry
# -------------------------------------------------------------
with tab_cuisine:
    col_cu1, col_cu2 = st.columns(2)
    
    with col_cu1:
        st.subheader("🍲 Most Dominant Cuisines")
        # Unroll cuisines
        cuisine_series = filtered_df['cuisines'].dropna().apply(lambda x: [c.strip() for c in str(x).split(',')])
        flat_cuisines = [c for sublist in cuisine_series for c in sublist if c]
        cuisine_counts = Counter(flat_cuisines).most_common(15)
        cu_df = pd.DataFrame(cuisine_counts, columns=['Cuisine', 'Occurrences'])
        
        fig_cu = px.pie(
            cu_df,
            names="Cuisine",
            values="Occurrences",
            hole=0.45,
            color_discrete_sequence=px.colors.qualitative.Prism,
            template=chart_template,
            title="Top 15 Cuisines Market Share"
        )
        fig_cu.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=20, r=20, t=40, b=20)
        )
        st.plotly_chart(fig_cu, use_container_width=True)

    with col_cu2:
        st.subheader("🍴 Top Liked Signature Dishes")
        dishes_series = filtered_df['dish_liked'].dropna().apply(lambda x: [d.strip() for d in str(x).split(',')])
        flat_dishes = [d for sublist in dishes_series for d in sublist if d]
        dish_counts = Counter(flat_dishes).most_common(15)
        dish_df = pd.DataFrame(dish_counts, columns=['Dish', 'Count'])
        
        if len(dish_df) > 0:
            fig_dish = px.bar(
                dish_df,
                x="Count",
                y="Dish",
                orientation='h',
                color="Count",
                color_continuous_scale="Sunset",
                template=chart_template,
                labels={"Dish": "Signature Dish", "Count": "Diner Endorsements"}
            )
            fig_dish.update_layout(
                yaxis=dict(autorange="reversed"),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=20, r=20, t=40, b=20)
            )
            st.plotly_chart(fig_dish, use_container_width=True)
        else:
            st.info("Dish feedback not available in the current subset.")

# -------------------------------------------------------------
# TAB 4: Operational Analytics
# -------------------------------------------------------------
with tab_operations:
    col_op1, col_op2 = st.columns(2)
    
    with col_op1:
        st.subheader("🛵 Delivery Mode vs Customer Satisfaction")
        fig_box_delivery = px.box(
            filtered_df.dropna(subset=['rating']),
            x="online_order",
            y="rating",
            color="online_order",
            color_discrete_map={"Yes": "#10b981", "No": "#ef4444"},
            template=chart_template,
            title="Rating Distribution by Online Order Availability",
            labels={"online_order": "Online Ordering Enabled", "rating": "Rating Score"}
        )
        fig_box_delivery.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=20, r=20, t=40, b=20)
        )
        st.plotly_chart(fig_box_delivery, use_container_width=True)

    with col_op2:
        st.subheader("📅 Table Reservation Impact on Engagement")
        fig_box_booking = px.box(
            filtered_df.dropna(subset=['votes']),
            x="book_table",
            y="votes",
            color="book_table",
            color_discrete_map={"Yes": "#3b82f6", "No": "#9ca3af"},
            template=chart_template,
            title="Customer Engagement (Votes) by Table Booking Option",
            labels={"book_table": "Table Booking Enabled", "votes": "Votes Cast"}
        )
        fig_box_booking.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            yaxis_type="log",
            margin=dict(l=20, r=20, t=40, b=20)
        )
        st.plotly_chart(fig_box_booking, use_container_width=True)

    st.subheader("🏷️ Price Tier Breakdown & Market Share")
    tier_counts = filtered_df['cost_tier'].value_counts().reset_index()
    tier_counts.columns = ['Price Tier', 'Count']
    
    fig_tier = px.bar(
        tier_counts,
        x="Price Tier",
        y="Count",
        color="Price Tier",
        color_discrete_sequence=px.colors.qualitative.Bold,
        template=chart_template,
        title="Restaurant Distribution across Dining Price Brackets"
    )
    fig_tier.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=40, b=20)
    )
    st.plotly_chart(fig_tier, use_container_width=True)

# -------------------------------------------------------------
# TAB 5: Data Explorer & Export
# -------------------------------------------------------------
with tab_data:
    st.subheader("🔍 Real-time Telemetry Data Grid")
    
    col_search, col_export = st.columns([3, 1])
    with col_search:
        st.markdown(f"Displaying **{len(filtered_df):,}** active records matching telemetry criteria.")
    with col_export:
        csv_data = filtered_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Export Filtered CSV",
            data=csv_data,
            file_name="telemetry_filtered_data.csv",
            mime="text/csv",
            use_container_width=True
        )

    # Show preview
    columns_to_show = [
        'name', 'city_zone', 'location', 'rating', 'votes', 
        'cost_for_two', 'online_order', 'book_table', 'service_type', 'cuisines'
    ]
    st.dataframe(
        filtered_df[columns_to_show].head(500),
        use_container_width=True,
        hide_index=True
    )
    
    st.markdown("---")
    st.subheader("🔬 Telemetry Telemetry Schema Health Check")
    health_col1, health_col2, health_col3 = st.columns(3)
    with health_col1:
        st.write("**Total Null Ratings:**", filtered_df['rating'].isna().sum())
    with health_col2:
        st.write("**Total Null Cost Values:**", filtered_df['cost_for_two'].isna().sum())
    with health_col3:
        st.write("**Memory Usage:**", f"{filtered_df.memory_usage().sum() / 1024 / 1024:.2f} MB")

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Climbing Dashboard", layout="wide", page_icon="🧗‍♂️")
st.title("🧗‍♂️ Climbing Tracking Dashboard")

# --- CARICAMENTO E PULIZIA DATI ---
SHEET_ID = "1aeCcRAt7baHVt3P75YTq_rSxSKOzwbjuCLpAcgIyc3Q"
URL_LINES = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=831695350"
URL_SESSIONS = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=1617924867"

@st.cache_data(ttl=600)
def load_and_clean_data():
    df_sessions = pd.read_csv(URL_SESSIONS)
    df_lines = pd.read_csv(URL_LINES)
    
    # 1. Date e Mesi
    df_sessions['date'] = pd.to_datetime(df_sessions['date'], errors='coerce')
    df_lines['date'] = pd.to_datetime(df_lines['date'], errors='coerce')
    df_sessions['month'] = df_sessions['date'].dt.to_period('M').astype(str)
    df_lines['month'] = df_lines['date'].dt.to_period('M').astype(str)

    # 2. Pulizia Stringhe (Lower case e strip spazi) per evitare errori di case-sensitivity
    string_cols = ['climbing_type', 'grade', 'status', 'climbing_style', 'holds_type']
    for col in string_cols:
        if col in df_lines.columns:
            df_lines[col] = df_lines[col].astype(str).str.lower().str.strip()
    
    # 3. Scala Corda
    list_grades_rope = [f"{n}{l}" for n in range(3, 9) for l in ["a", "a+", "b", "b+", "c", "c+"]]
    grade_order_rope = {grade: i for i, grade in enumerate(list_grades_rope)}
    
    # 4. Scala Boulder
    list_grades_boulder = ['blu', 'verde', 'gialla']
    grade_order_boulder = {grade: i for i, grade in enumerate(list_grades_boulder)}
    
    return df_sessions, df_lines, list_grades_rope, grade_order_rope, list_grades_boulder, grade_order_boulder

# Caricamento
df_sessions, df_lines, list_grades_rope, grade_order_rope, list_grades_boulder, grade_order_boulder = load_and_clean_data()

# --- MAPPE COLORI ---
color_map_boulder = {'blu': '#1f77b4', 'verde': '#2ca02c', 'gialla': '#ffd700'}
color_map_status = {
    'on sight': '#1f77b4', 
    'flash': '#2ca02c',    
    'redpoint': '#d62728', 
    'red point': '#d62728' 
}

# --- SIDEBAR GENERALE ---
st.sidebar.header("Filtri Globali")
available_types_global = df_lines['climbing_type'].dropna().unique()
# Scegliamo un default sicuro (es. se rock climbing non c'è, prende il primo disponibile)
default_type_global = ['rock climbing'] if 'rock climbing' in available_types_global else (available_types_global[:1] if len(available_types_global)>0 else [])
selected_type = st.sidebar.multiselect("Tipo di Arrampicata", available_types_global, default=default_type_global)
df_filtered = df_lines[df_lines['climbing_type'].isin(selected_type)]


# --- SEZIONE 1: GENERALE ---
st.header("📊 Overview Volume")
df_vol = df_lines.groupby(['month', 'climbing_type'])['session_id'].nunique().reset_index(name='sessions')
df_vol = df_vol.sort_values('month')
fig_vol = px.bar(df_vol, x='month', y='sessions', color='climbing_type', 
                 title="Numero di Sessioni Mensili", barmode='stack')
fig_vol.update_layout(xaxis_title="Mese", yaxis_title="Sessioni", legend_title="Tipo", margin=dict(l=0, r=0, t=40, b=0))
st.plotly_chart(fig_vol, use_container_width=True)


# --- SEZIONE 2: CORDA ---
st.header("🪢 Arrampicata su Corda")
df_rope = df_lines[df_lines['climbing_type'].isin(['rock climbing', 'indoor climbing'])].copy()
df_rope['grade_numeric'] = df_rope['grade'].map(grade_order_rope)

with st.expander("🔍 Filtri Corda"):
    available_types = df_rope['climbing_type'].dropna().unique()
    r_types = st.multiselect("Ambiente", available_types, default=available_types)
    
    available_status = df_rope['status'].dropna().unique()
    safe_defaults_status = [s for s in ['on sight', 'flash', 'redpoint'] if s in available_status]
    r_status = st.multiselect("Status", available_status, default=safe_defaults_status)
    
    available_styles = df_rope['climbing_style'].dropna().unique()
    r_style = st.multiselect("Stile", available_styles, default=available_styles)
    
    available_holds = df_rope['holds_type'].dropna().unique()
    r_holds = st.multiselect("Prese", available_holds, default=available_holds)

df_rope_filt = df_rope[
    (df_rope['climbing_type'].isin(r_types)) &
    (df_rope['status'].isin(r_status)) &
    (df_rope['climbing_style'].isin(r_style) if len(r_style) > 0 else True) &
    (df_rope['holds_type'].isin(r_holds) if len(r_holds) > 0 else True)
]

if not df_rope_filt.empty:
    df_pyramid = df_rope_filt.groupby('grade').size().reset_index(name='count')
    df_pyramid['numeric'] = df_pyramid['grade'].map(grade_order_rope)
    df_pyramid = df_pyramid.sort_values('numeric', ascending=True)
    fig_pyr = px.bar(df_pyramid, x='count', y='grade', orientation='h', title="Piramide dei Gradi Globale", text='count')
    fig_pyr.update_layout(margin=dict(l=0, r=0, t=40, b=0))
    st.plotly_chart(fig_pyr, use_container_width=True)

    df_pyr_month = df_rope_filt.groupby(['month', 'grade']).size().reset_index(name='count')
    fig_pyr_m = px.bar(df_pyr_month, x='month', y='count', color='grade', title="Volume Gradi per Mese",
                       category_orders={'grade': list_grades_rope})
    fig_pyr_m.update_layout(margin=dict(l=0, r=0, t=40, b=0))
    st.plotly_chart(fig_pyr_m, use_container_width=True)

    df_max = df_rope_filt.groupby(['month'])['grade_numeric'].max().reset_index()
    reverse_rope = {v: k for k, v in grade_order_rope.items()}
    df_max['max_grade'] = df_max['grade_numeric'].map(reverse_rope)
    fig_max = px.line(df_max, x='month', y='max_grade', markers=True, title="Grado Massimo Mensile Assoluto",
                      category_orders={'max_grade': list_grades_rope})
    fig_max.update_layout(margin=dict(l=0, r=0, t=40, b=0))
    st.plotly_chart(fig_max, use_container_width=True)

    df_max_stat = df_rope_filt.groupby(['month', 'status'])['grade_numeric'].max().reset_index()
    df_max_stat['max_grade'] = df_max_stat['grade_numeric'].map(reverse_rope)
    fig_max_stat = px.line(df_max_stat, x='month', y='max_grade', color='status', markers=True, 
                           title="Max Grado Mensile per Status",
                           color_discrete_map=color_map_status,
                           category_orders={'max_grade': list_grades_rope})
    fig_max_stat.update_layout(margin=dict(l=0, r=0, t=40, b=0))
    st.plotly_chart(fig_max_stat, use_container_width=True)
else:
    st.info("Nessun dato per i filtri selezionati.")


# --- SEZIONE 3: BOULDER ---
st.markdown("---")
st.header("🧗‍♂️ Boulder")

df_boulder = df_lines[df_lines['climbing_type'].isin(['indoor boulder', 'rock boulder'])].copy()
df_boulder = df_boulder[df_boulder['grade'].isin(list_grades_boulder)]
df_boulder['grade_numeric'] = df_boulder['grade'].map(grade_order_boulder)

with st.expander("🔍 Filtri Boulder"):
    available_b_types = df_boulder['climbing_type'].dropna().unique()
    b_types = st.multiselect("Ambiente Boulder", available_b_types, default=available_b_types)
    
    available_b_status = df_boulder['status'].dropna().unique()
    safe_defaults_b_status = [s for s in ['on sight', 'flash', 'redpoint'] if s in available_b_status]
    b_status = st.multiselect("Status Boulder", available_b_status, default=safe_defaults_b_status)

df_boulder_filt = df_boulder[
    (df_boulder['climbing_type'].isin(b_types)) &
    (df_boulder['status'].isin(b_status))
]

if not df_boulder_filt.empty:
    df_bp_month = df_boulder_filt.groupby(['month', 'grade']).size().reset_index(name='count')
    fig_bp_m = px.bar(df_bp_month, x='month', y='count', color='grade', title="Volume Blocchi per Mese",
                      color_discrete_map=color_map_boulder, category_orders={'grade': list_grades_boulder})
    fig_bp_m.update_layout(margin=dict(l=0, r=0, t=40, b=0))
    st.plotly_chart(fig_bp_m, use_container_width=True)

    df_bm_stat = df_boulder_filt.groupby(['month', 'status'])['grade_numeric'].max().reset_index()
    reverse_boulder = {v: k for k, v in grade_order_boulder.items()}
    df_bm_stat['max_grade'] = df_bm_stat['grade_numeric'].map(reverse_boulder)
    fig_bm_stat = px.line(df_bm_stat, x='month', y='max_grade', color='status', markers=True, 
                          title="Max Colore Mensile per Status",
                          color_discrete_map=color_map_status,
                          category_orders={'max_grade': list_grades_boulder})
    fig_bm_stat.update_layout(margin=dict(l=0, r=0, t=40, b=0))
    st.plotly_chart(fig_bm_stat, use_container_width=True)  
else:
    st.info("Nessun dato per i filtri selezionati.")


# --- SEZIONE 4: MULTIPITCH ---
st.markdown("---")
st.header("⛰️ Multipitch & Trad")

df_multi = df_lines[df_lines['climbing_type'] == 'multipitch'].copy()

if not df_multi.empty:
    df_multi['is_trad'] = df_multi['comment'].astype(str).str.contains(r'trad|integrare', case=False, na=False)
    
    col_a, col_b = st.columns(2)
    col_a.metric("Totale Vie Lunghe", len(df_multi))
    col_b.metric("Di cui Trad/Integrare", df_multi['is_trad'].sum())
    
    df_multi_view = df_multi[['date', 'description', 'grade', 'comment', 'is_trad']].sort_values('date', ascending=False)
    df_multi_view['date'] = df_multi_view['date'].dt.strftime('%d/%m/%Y')
    
    def format_description(row):
        return f"🛡️ {row['description']}" if row['is_trad'] else row['description']
        
    df_multi_view['description'] = df_multi_view.apply(format_description, axis=1)
    df_multi_view = df_multi_view.rename(columns={'date': 'Data', 'description': 'Via', 'grade': 'Grado', 'comment': 'Note'})
    
    st.dataframe(df_multi_view[['Data', 'Via', 'Grado', 'Note']], use_container_width=True, hide_index=True)
else:
    st.info("Nessuna via lunga registrata finora.")